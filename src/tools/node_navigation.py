"""Node-neighbor tools for navigating document chunks by node_id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.extract.content_loader import get_node_pages, get_node_text
from src.tools.registry import get_doc_config


MAX_STEPS = 5
TEXT_TRUNCATE_LIMIT = 4000


def get_prev_node(
    doc_name: str,
    node_id: str,
    steps: int = 1,
    include_text: bool = True,
) -> dict[str, Any]:
    """Return the previous document node in flattened outline order."""

    return _get_adjacent_node(
        doc_name=doc_name,
        node_id=node_id,
        steps=steps,
        include_text=include_text,
        direction=-1,
    )


def get_next_node(
    doc_name: str,
    node_id: str,
    steps: int = 1,
    include_text: bool = True,
) -> dict[str, Any]:
    """Return the next document node in flattened outline order."""

    return _get_adjacent_node(
        doc_name=doc_name,
        node_id=node_id,
        steps=steps,
        include_text=include_text,
        direction=1,
    )


def _get_adjacent_node(
    *,
    doc_name: str,
    node_id: str,
    steps: int,
    include_text: bool,
    direction: int,
) -> dict[str, Any]:
    config = get_doc_config(doc_name)
    if "error" in config:
        return config

    target_id = str(node_id or "").strip()
    if not target_id:
        return {"error": "node_id is required."}

    try:
        step_count = int(steps)
    except (TypeError, ValueError):
        step_count = 1
    step_count = max(1, min(MAX_STEPS, step_count))

    nodes = _load_flat_nodes(str(config["chunks_dir"]))
    if not nodes:
        return {"error": f"No document nodes found for {doc_name}."}

    index_by_id = {
        str(node.get("node_id", "") or "").strip(): index
        for index, node in enumerate(nodes)
        if str(node.get("node_id", "") or "").strip()
    }
    current_index = index_by_id.get(target_id)
    if current_index is None:
        return {
            "error": f"Node not found: {target_id}",
            "known_node_id_preview": list(index_by_id.keys())[:20],
        }

    target_index = current_index + (direction * step_count)
    if target_index < 0 or target_index >= len(nodes):
        return {
            "target_node_id": target_id,
            "direction": "previous" if direction < 0 else "next",
            "steps": step_count,
            "node": None,
            "position": current_index + 1,
            "total_nodes": len(nodes),
            "boundary": "start" if target_index < 0 else "end",
        }

    adjacent = nodes[target_index]
    return {
        "target_node_id": target_id,
        "direction": "previous" if direction < 0 else "next",
        "steps": step_count,
        "position": target_index + 1,
        "total_nodes": len(nodes),
        "node": _node_record(
            adjacent,
            content_dir=str(config["content_dir"]),
            include_text=include_text,
        ),
        "context": {
            "previous_node_id": _node_id_at(nodes, target_index - 1),
            "current_node_id": str(adjacent.get("node_id", "") or ""),
            "next_node_id": _node_id_at(nodes, target_index + 1),
        },
        "next_steps": (
            "Use get_prev_node/get_next_node again to walk neighboring sections. "
            "Use returned source_pages in patch proposals when evidence_text comes from this node."
        ),
    }


def _load_flat_nodes(chunks_dir: str) -> list[dict[str, Any]]:
    chunks_path = Path(chunks_dir)
    if not chunks_path.exists():
        return []

    files = _part_files(chunks_path)
    nodes: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        structure = payload.get("structure", [])
        if isinstance(structure, list):
            for item in structure:
                _append_flat_node(item, nodes)
    return nodes


def _part_files(chunks_path: Path) -> list[Path]:
    manifest_path = chunks_path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        files = manifest.get("files", [])
        if isinstance(files, list):
            paths = [chunks_path / str(name) for name in files]
            existing = [path for path in paths if path.exists()]
            if existing:
                return existing
    return sorted(chunks_path.glob("part_*.json"))


def _append_flat_node(item: Any, out: list[dict[str, Any]]) -> None:
    if not isinstance(item, dict):
        return
    out.append(item)
    children = item.get("children", [])
    if isinstance(children, list):
        for child in children:
            _append_flat_node(child, out)


def _node_record(node: dict[str, Any], *, content_dir: str, include_text: bool) -> dict[str, Any]:
    pages = get_node_pages(node)
    record: dict[str, Any] = {
        "node_id": str(node.get("node_id", "") or ""),
        "title": str(node.get("title", "") or ""),
        "summary": str(node.get("summary", "") or ""),
        "source_pages": pages,
        "start_index": node.get("start_index"),
        "end_index": node.get("end_index"),
        "start_line": node.get("start_line"),
        "end_line": node.get("end_line"),
    }
    if include_text:
        text = get_node_text(node, content_dir) or ""
        record["text"] = _truncate_text(text)
    return record


def _truncate_text(text: str) -> str:
    if len(text) <= TEXT_TRUNCATE_LIMIT:
        return text
    return text[: TEXT_TRUNCATE_LIMIT - 15].rstrip() + "\n...[truncated]"


def _node_id_at(nodes: list[dict[str, Any]], index: int) -> str:
    if index < 0 or index >= len(nodes):
        return ""
    return str(nodes[index].get("node_id", "") or "")
