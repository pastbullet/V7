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


def _build_runner_fixture(root: Path) -> None:
    doc_root = root / "processed_specs" / "demo" / "demo_doc"
    _write_json(
        doc_root / "pages" / "page_001" / "text.json",
        {
            "doc_id": "demo_doc",
            "page": 1,
            "spans": [
                {
                    "span_id": "p001_s001",
                    "text": "FLOGI completes when LS_ACC is received.",
                    "bbox": [10, 20, 300, 40],
                }
            ],
            "asset_ids": ["table_0001"],
        },
    )
    _write_text(doc_root / "pages" / "page_001" / "page.png", "fake page")
    _write_text(
        doc_root / "assets" / "assets_manifest.jsonl",
        json.dumps(
            {
                "asset_id": "table_0001",
                "type": "table",
                "caption": "Table 1 Demo Payload",
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
            "caption": "Table 1 Demo Payload",
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
                "cell_id": "r1c2",
                "row": 1,
                "col": 2,
                "text": "LS_ACC",
                "page": 1,
                "bbox": [90, 80, 130, 100],
            }
        )
        + "\n",
    )


def test_extract_json_payload_accepts_fenced_json():
    from src.reading.runner import extract_json_payload

    payload = extract_json_payload(
        "Here is the payload:\n```json\n{\"doc_id\":\"demo_doc\",\"claim_candidates\":[]}\n```"
    )

    assert payload["doc_id"] == "demo_doc"
    assert payload["claim_candidates"] == []


def test_run_reading_claim_agent_materializes_llm_payload(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_runner_fixture(tmp_path)

    from src.reading import runner

    calls: list[dict] = []

    async def fake_agentic_rag(**kwargs):
        calls.append(kwargs)
        return RAGResponse(
            answer=json.dumps(
                {
                    "doc_id": "demo_doc",
                    "unit_id": "flogi",
                    "reading_md": "# FLOGI\n\nRead with tools.",
                    "claim_candidates": [
                        {
                            "claim_id": "c1",
                            "text": "FLOGI completes when LS_ACC is received.",
                            "kind": "completion_condition",
                            "evidence_refs": [
                                {
                                    "type": "text_span",
                                    "span_id": "p001_s001",
                                    "quote": "LS_ACC is received",
                                }
                            ],
                        },
                        {
                            "claim_id": "c2",
                            "text": "The payload table includes LS_ACC.",
                            "kind": "field_value",
                            "evidence_refs": [
                                {
                                    "type": "table_cell",
                                    "asset_id": "table_0001",
                                    "cell_id": "r1c2",
                                    "quote": "LS_ACC",
                                }
                            ],
                        },
                    ],
                }
            ),
            answer_clean="",
            total_turns=3,
        )

    monkeypatch.setattr(runner, "agentic_rag", fake_agentic_rag)

    output_dir = tmp_path / "readings" / "flogi"
    result = asyncio.run(
        runner.run_reading_claim_agent(
            doc_name="demo_doc",
            unit_id="flogi",
            reading_goal="Read FLOGI completion and payload facts.",
            output_dir=output_dir,
            model="fake-model",
        )
    )

    assert result["accepted_count"] == 2
    assert calls[0]["doc_name"] == "demo_doc"
    assert calls[0]["prompt_file"] == "reading_claim_system.txt"
    assert "get_document_structure" in calls[0]["system_prompt_override"]
    assert "search_nodes" not in calls[0]["system_prompt_override"]
    assert json.loads((output_dir / "llm_payload.json").read_text(encoding="utf-8"))["unit_id"] == "flogi"
    assert (output_dir / "reading.md").read_text(encoding="utf-8").startswith("# FLOGI")
    claims = [
        json.loads(line)
        for line in (output_dir / "claims.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [claim["claim_id"] for claim in claims] == ["c1", "c2"]
