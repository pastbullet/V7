from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_claim_fixture(root: Path) -> None:
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
            "asset_ids": ["table_0001", "figure_0001"],
        },
    )
    _write_text(doc_root / "pages" / "page_001" / "page.png", "fake page image")
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
        + "\n"
        + json.dumps(
            {
                "asset_id": "figure_0001",
                "type": "figure",
                "caption": "Figure 1 Demo Flow",
                "pages": [1],
                "path": "figures/figure_0001/figure_meta.json",
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
    _write_json(
        doc_root / "figures" / "figure_0001" / "figure_meta.json",
        {
            "asset_id": "figure_0001",
            "type": "figure",
            "caption": "Figure 1 Demo Flow",
            "pages": [1],
            "bbox": [10, 180, 300, 360],
            "source_crop": "crop.png",
            "context_file": "context.md",
            "vision_summary_file": "vision_summary.json",
        },
    )
    _write_text(doc_root / "figures" / "figure_0001" / "crop.png", "fake figure crop")
    _write_text(doc_root / "figures" / "figure_0001" / "context.md", "")
    _write_json(doc_root / "figures" / "figure_0001" / "vision_summary.json", {"derived": True})


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_materialize_reading_claims_writes_only_verified_claims(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_claim_fixture(tmp_path)

    from src.reading.claims import materialize_reading_claims

    output_dir = tmp_path / "readings" / "flogi"
    result = materialize_reading_claims(
        doc_id="demo_doc",
        unit_id="flogi",
        reading_md="# FLOGI\n\nHuman-readable explanation.",
        claim_candidates=[
            {
                "claim_id": "c_text",
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
                "claim_id": "c_cell",
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
        output_dir=output_dir,
    )

    assert result["accepted_count"] == 2
    assert (output_dir / "reading.md").read_text(encoding="utf-8").startswith("# FLOGI")
    accepted = _read_jsonl(output_dir / "claims.jsonl")
    assert [claim["claim_id"] for claim in accepted] == ["c_text", "c_cell"]
    evidence_map = json.loads((output_dir / "evidence_map.json").read_text(encoding="utf-8"))
    assert evidence_map["c_cell"][0]["type"] == "table_cell"
    verify_report = json.loads((output_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert verify_report["accepted_count"] == 2
    assert verify_report["invalid_count"] == 0
    assert verify_report["unresolved_count"] == 0


def test_materialize_reading_claims_separates_unresolved_and_invalid_refs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_claim_fixture(tmp_path)

    from src.reading.claims import materialize_reading_claims

    output_dir = tmp_path / "readings" / "flogi"
    materialize_reading_claims(
        doc_id="demo_doc",
        unit_id="flogi",
        reading_md="# FLOGI\n\nDo not cite this file as evidence.",
        claim_candidates=[
            {
                "claim_id": "missing_evidence",
                "text": "This should not enter accepted claims.",
                "kind": "response_branch",
                "evidence_refs": [],
            },
            {
                "claim_id": "derived_source",
                "text": "Derived summaries are not raw facts.",
                "kind": "diagram_fact",
                "evidence_refs": [{"type": "vision_summary", "asset_id": "figure_0001"}],
            },
            {
                "claim_id": "explicit_unresolved",
                "text": "Needs more source evidence.",
                "kind": "field_constraint",
                "status": "unresolved",
                "reason": "source span not found",
                "evidence_refs": [],
            },
        ],
        output_dir=output_dir,
    )

    assert _read_jsonl(output_dir / "claims.jsonl") == []
    unresolved = json.loads((output_dir / "unresolved.json").read_text(encoding="utf-8"))
    assert {item["claim_id"] for item in unresolved["items"]} == {
        "missing_evidence",
        "explicit_unresolved",
    }
    verify_report = json.loads((output_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert verify_report["accepted_count"] == 0
    assert verify_report["invalid_count"] == 1
    assert verify_report["unresolved_count"] == 2
    assert "not an allowed raw evidence type" in verify_report["invalid"][0]["invalid_refs"][0]["reason"]


def test_reading_claims_cli_materializes_payload(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_claim_fixture(tmp_path)
    payload_path = tmp_path / "payload.json"
    output_dir = tmp_path / "readings" / "flogi"
    _write_json(
        payload_path,
        {
            "doc_id": "demo_doc",
            "unit_id": "flogi",
            "reading_md": "# FLOGI\n\nCLI generated reading.",
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
                }
            ],
        },
    )

    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.reading.claims",
            "--input",
            str(payload_path),
            "--out",
            str(output_dir),
        ],
        cwd=tmp_path,
        env={"PYTHONPATH": str(repo_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "accepted_count" in completed.stdout
    claims = _read_jsonl(output_dir / "claims.jsonl")
    assert claims[0]["claim_id"] == "c1"
