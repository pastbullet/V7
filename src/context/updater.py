"""Updater — maps tool-call events to state update operations.

The Updater sits between the ContextManager and the individual stores,
routing each tool call to the appropriate handler based on tool_name.
Unknown tools are logged as warnings and silently skipped.
"""

from __future__ import annotations

import logging

from src.context.stores.document_store import DocumentStore
from src.context.stores.evidence_store import EvidenceStore
from src.context.stores.turn_store import TurnStore
from src.tools.page_content import parse_pages

logger = logging.getLogger(__name__)

ASSET_AND_VERIFICATION_TOOLS = {"list_assets", "get_table", "get_image", "verify_evidence"}


def _parse_pages_spec(pages_spec: object) -> list[int]:
    """Best-effort parse for page specs used by get_page_content.

    Supports:
    - int: 7
    - str: "7", "7-11", "7,9,11", "36,166-170,179,203"
    - list: [7, 8, "9"]
    """
    if isinstance(pages_spec, int):
        return [pages_spec]

    if isinstance(pages_spec, list):
        out: set[int] = set()
        for item in pages_spec:
            if isinstance(item, int):
                out.add(item)
            elif isinstance(item, str):
                try:
                    out.update(parse_pages(item))
                except (TypeError, ValueError):
                    continue
        return sorted(out)

    if not isinstance(pages_spec, str):
        return []

    spec = pages_spec.strip()
    if not spec:
        return []

    try:
        return parse_pages(spec)
    except (TypeError, ValueError):
        return []


class Updater:
    """Maps tool-call events to state update operations."""

    def __init__(
        self,
        document_store: DocumentStore,
        turn_store: TurnStore,
        evidence_store: EvidenceStore,
    ) -> None:
        self._document_store = document_store
        self._turn_store = turn_store
        self._evidence_store = evidence_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_tool_call(
        self,
        turn_id: str,
        tool_name: str,
        arguments: dict,
        result: dict,
        doc_id: str | None = None,
    ) -> None:
        """Route a tool call to the appropriate handler.

        Parameters
        ----------
        turn_id:
            Current turn identifier.
        tool_name:
            Name of the tool that was called.
        arguments:
            Arguments passed to the tool.
        result:
            Result returned by the tool.
        doc_id:
            Document identifier (required for document-related tools).
        """
        if tool_name == "get_document_structure":
            self._handle_document_structure(turn_id, arguments, result, doc_id)
        elif tool_name == "search_nodes":
            self._handle_search_nodes(turn_id, arguments, result, doc_id)
        elif tool_name == "get_page_content":
            self._handle_page_content(turn_id, arguments, result, doc_id)
        elif tool_name in ASSET_AND_VERIFICATION_TOOLS:
            self._handle_asset_or_verification_tool(turn_id, tool_name, arguments, result, doc_id)
        else:
            logger.warning("Unknown tool '%s', skipping state update", tool_name)

    def handle_final_answer(self, turn_id: str, answer_payload: dict) -> None:
        """Handle a final_answer event.

        This is a placeholder — the actual finalisation logic (evidence
        usage, topic snapshot) will be driven by ContextManager.

        Parameters
        ----------
        turn_id:
            The turn being finalised.
        answer_payload:
            The final answer data.
        """
        logger.info(
            "Final answer handled for turn '%s'", turn_id
        )

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    def _handle_document_structure(
        self, turn_id: str, arguments: dict, result: dict, doc_id: str
    ) -> None:
        """Process a ``get_document_structure`` result.

        1. Validate that *result* has no ``"error"`` key and that
           ``result["structure"]`` is a list.
        2. Flatten the structure tree via DocumentStore.
        3. Upsert each node (respecting skeleton merge rules).
        4. Update visited parts on the document.
        5. Write back the turn's retrieval_trace.
        """
        # --- Validation ---
        if "error" in result:
            logger.warning(
                "get_document_structure returned error for doc '%s': %s",
                doc_id,
                result["error"],
            )
            return

        structure = result.get("structure")
        if not isinstance(structure, list):
            logger.warning(
                "get_document_structure result.structure is not a list for doc '%s'",
                doc_id,
            )
            return

        # --- Flatten ---
        flat_nodes = self._document_store.flatten_structure(structure)

        # --- Upsert each node ---
        collected_node_ids: list[str] = []
        for node in flat_nodes:
            node_data = {
                "node_id": node.get("node_id"),
                "title": node["title"],
                "start_index": node.get("start_index", 0),
                "end_index": node.get("end_index", 0),
                "summary": node.get("summary"),
                "is_skeleton": node.get("is_skeleton", True),
                "parent_path": node.get("parent_path", ""),
            }
            actual_node_id = self._document_store.upsert_node(
                doc_id, node_data, turn_id
            )
            collected_node_ids.append(actual_node_id)

        # --- Update visited parts ---
        part = arguments.get("part")
        if part is not None:
            self._document_store.update_visited_parts(doc_id, part)

        # --- Write back retrieval trace ---
        self._turn_store.update_retrieval_trace(
            turn_id,
            parts_seen=[part] if part is not None else None,
            candidate_nodes=collected_node_ids if collected_node_ids else None,
        )

    def _handle_search_nodes(
        self, turn_id: str, arguments: dict, result: dict, doc_id: str
    ) -> None:
        """Process a ``search_nodes`` result as navigation candidates only."""
        if "error" in result:
            logger.warning(
                "search_nodes returned error for doc '%s': %s",
                doc_id,
                result["error"],
            )
            return

        results = result.get("results")
        if not isinstance(results, list):
            logger.warning("search_nodes result.results is not a list for doc '%s'", doc_id)
            return

        candidate_nodes: list[str] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            node_id = item.get("node_id")
            if isinstance(node_id, str) and node_id.strip():
                candidate_nodes.append(node_id.strip())

        self._turn_store.update_retrieval_trace(
            turn_id,
            candidate_nodes=candidate_nodes if candidate_nodes else None,
        )

    def _handle_page_content(
        self, turn_id: str, arguments: dict, result: dict, doc_id: str
    ) -> None:
        """Process a ``get_page_content`` result.

        1. Determine which pages were read from *arguments*.
        2. Update read_pages on the document.
        3. Update node read status if a node_id is available.
        4. Write back the turn's retrieval_trace.
        """
        # --- Determine pages ---
        # Prefer concrete pages from tool result; fall back to arguments parsing.
        pages: list[int] = []
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    page = item.get("page")
                    if isinstance(page, int):
                        pages.append(page)

        if not pages:
            if "page" in arguments:
                pages = _parse_pages_spec(arguments.get("page"))
            else:
                pages = _parse_pages_spec(arguments.get("pages"))

        # --- Update read pages ---
        if pages:
            self._document_store.update_read_pages(doc_id, pages)

        # --- Update node read status ---
        if pages and doc_id:
            try:
                for node_id in self._document_store.find_nodes_covering_pages(doc_id, pages):
                    self._document_store.update_node_read_status(doc_id, node_id)
            except Exception as exc:
                logger.warning(
                    "Node status update failed for doc '%s': %s",
                    doc_id,
                    exc,
                )

        # --- Write back retrieval trace ---
        self._turn_store.update_retrieval_trace(
            turn_id,
            pages_read=pages if pages else None,
        )

    def _handle_asset_or_verification_tool(
        self,
        turn_id: str,
        tool_name: str,
        arguments: dict,
        result: dict,
        doc_id: str,
    ) -> None:
        """Recognize asset/evidence tools without marking source pages as read.

        These tools inspect asset manifests, table/figure artifacts, or structural
        evidence refs. They are already recorded in the turn's tool_calls by
        ContextManager.record_tool_call; the current context state has no asset
        store, so this handler is intentionally a no-op.
        """
        logger.debug(
            "Recognized %s for doc '%s'; no context state update required",
            tool_name,
            doc_id,
        )
