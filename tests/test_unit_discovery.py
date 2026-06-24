from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.models import RAGResponse


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_discovery_fixture(root: Path) -> None:
    doc_root = root / "processed_specs" / "demo" / "demo_doc"
    _write_json(
        doc_root / "pages" / "page_001" / "text.json",
        {
            "doc_id": "demo_doc",
            "page": 1,
            "spans": [
                {
                    "span_id": "p001_s001",
                    "text": "Clause 4.2.7 describes the FLOGI request and LS_ACC response.",
                    "bbox": [10, 20, 360, 40],
                }
            ],
            "asset_ids": ["table_0001"],
        },
    )
    _write_text(doc_root / "pages" / "page_001" / "page.png", "fake page image")
    _write_text(
        doc_root / "assets" / "assets_manifest.jsonl",
        json.dumps(
            {
                "asset_id": "table_0001",
                "type": "table",
                "caption": "Table 1 Demo Login Payload",
                "pages": [1],
                "path": "tables/table_0001/table_meta.json",
            }
        )
        + "\n",
    )
    _write_json(
        doc_root / "tables" / "table_0001" / "table_meta.json",
        {
            "asset_id": "table_0001",
            "type": "table",
            "caption": "Table 1 Demo Login Payload",
            "pages": [1],
            "bbox": [10, 60, 300, 160],
            "source_crop": "crop.png",
            "context_file": "context.md",
        },
    )
    _write_text(doc_root / "tables" / "table_0001" / "crop.png", "fake table crop")
    _write_text(doc_root / "tables" / "table_0001" / "context.md", "")
    _write_text(
        doc_root / "tables" / "table_0001" / "cells.jsonl",
        json.dumps(
            {
                "cell_id": "r1c1",
                "row": 1,
                "col": 1,
                "text": "ELS_Command code",
                "page": 1,
                "bbox": [20, 80, 120, 100],
            }
        )
        + "\n",
    )


def test_materialize_unit_discovery_verifies_raw_evidence_and_assets(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_discovery_fixture(tmp_path)

    from src.discovery.units import materialize_unit_discovery

    output_dir = tmp_path / "discoveries" / "demo"
    result = materialize_unit_discovery(
        doc_id="demo_doc",
        discovery_md="# Discovery\n\nCandidate units found by the reader.",
        unit_candidates=[
            {
                "unit_id": "flogi",
                "title": "FLOGI request/response flow",
                "kind": "protocol_unit",
                "reason": "The cited span names the request and response.",
                "evidence_refs": [
                    {
                        "type": "text_span",
                        "span_id": "p001_s001",
                        "quote": "FLOGI request and LS_ACC response",
                    }
                ],
                "related_assets": [{"type": "table", "asset_id": "table_0001"}],
            },
            {
                "unit_id": "no_evidence",
                "title": "No evidence unit",
                "kind": "protocol_unit",
                "evidence_refs": [],
                "related_assets": [],
            },
            {
                "unit_id": "bad_asset",
                "title": "Bad asset unit",
                "kind": "protocol_unit",
                "evidence_refs": [
                    {
                        "type": "table_cell",
                        "asset_id": "table_0001",
                        "cell_id": "r1c1",
                        "quote": "ELS_Command code",
                    }
                ],
                "related_assets": [{"type": "table", "asset_id": "missing_table"}],
            },
        ],
        output_dir=output_dir,
    )

    assert result == {"output_dir": str(output_dir), "accepted_count": 1, "unresolved_count": 1, "invalid_count": 1}
    assert (output_dir / "discovery.md").read_text(encoding="utf-8").startswith("# Discovery")
    discovered = json.loads((output_dir / "discovered_units.json").read_text(encoding="utf-8"))
    assert [unit["unit_id"] for unit in discovered["units"]] == ["flogi"]
    assert discovered["units"][0]["related_assets"] == [{"type": "table", "asset_id": "table_0001"}]
    unresolved = json.loads((output_dir / "unresolved.json").read_text(encoding="utf-8"))
    assert unresolved["items"][0]["unit_id"] == "no_evidence"
    report = json.loads((output_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert report["accepted_count"] == 1
    assert report["unresolved_count"] == 1
    assert report["invalid_count"] == 1
    assert "missing_table" in report["invalid"][0]["invalid_assets"][0]["asset_id"]


def test_run_unit_discovery_agent_uses_discovery_prompt_and_materializes_payload(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_discovery_fixture(tmp_path)

    from src.discovery import runner

    calls: list[dict] = []

    async def fake_agentic_rag(**kwargs):
        calls.append(kwargs)
        return RAGResponse(
            answer=json.dumps(
                {
                    "doc_id": "demo_doc",
                    "discovery_md": "# Discovery\n\nThe unit is grounded in page/span evidence.",
                    "unit_candidates": [
                        {
                            "unit_id": "flogi",
                            "title": "FLOGI request/response flow",
                            "kind": "protocol_unit",
                            "reason": "The cited span names the request and response.",
                            "evidence_refs": [
                                {
                                    "type": "text_span",
                                    "span_id": "p001_s001",
                                    "quote": "FLOGI request and LS_ACC response",
                                }
                            ],
                            "related_assets": [{"type": "table", "asset_id": "table_0001"}],
                        }
                    ],
                }
            ),
            answer_clean="",
            total_turns=4,
        )

    monkeypatch.setattr(runner, "agentic_rag", fake_agentic_rag)

    output_dir = tmp_path / "discoveries" / "demo"
    result = asyncio.run(
        runner.run_unit_discovery_agent(
            doc_name="demo_doc",
            discovery_goal="Discover protocol units and relevant tables/figures.",
            output_dir=output_dir,
            model="fake-discovery-model",
        )
    )

    assert result["accepted_count"] == 1
    assert result["llm_turns"] == 4
    assert calls[0]["doc_name"] == "demo_doc"
    assert calls[0]["model"] == "fake-discovery-model"
    assert calls[0]["prompt_file"] == "unit_discovery_system.txt"
    assert "get_document_structure" in calls[0]["system_prompt_override"]
    assert "list_assets" in calls[0]["system_prompt_override"]
    assert "search_nodes" not in calls[0]["system_prompt_override"]
    payload = json.loads((output_dir / "llm_payload.json").read_text(encoding="utf-8"))
    assert payload["unit_candidates"][0]["unit_id"] == "flogi"
