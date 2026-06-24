from __future__ import annotations

import logging

from src.context.stores.document_store import DocumentStore
from src.context.stores.evidence_store import EvidenceStore
from src.context.stores.turn_store import TurnStore
from src.context.updater import Updater, _parse_pages_spec


def _make_updater(tmp_path):
    session_dir = tmp_path / "session"
    turn_store = TurnStore(session_dir / "turns")
    turn_store.create_turn("turn_0001", "question", "demo_doc")
    return Updater(
        document_store=DocumentStore(session_dir),
        turn_store=turn_store,
        evidence_store=EvidenceStore(session_dir / "evidences"),
    )


def test_context_page_parser_accepts_mixed_comma_ranges():
    assert _parse_pages_spec("36,166-170,179,203") == [36, 166, 167, 168, 169, 170, 179, 203]


def test_context_updater_recognizes_asset_and_verification_tools_without_marking_pages(tmp_path, caplog):
    updater = _make_updater(tmp_path)

    caplog.set_level(logging.WARNING, logger="src.context.updater")
    for tool_name in ("list_assets", "get_table", "get_image", "verify_evidence"):
        updater.handle_tool_call(
            "turn_0001",
            tool_name,
            {},
            {"ok": True},
            doc_id="demo_doc",
        )

    assert "Unknown tool" not in caplog.text
    state = DocumentStore(tmp_path / "session").get_document_state("demo_doc")
    assert state is None
