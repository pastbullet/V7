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


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _build_fixture(root: Path) -> None:
    doc_root = root / "processed_specs" / "demo" / "demo_doc"
    _write_json(
        doc_root / "pages" / "page_001" / "text.json",
        {
            "doc_id": "demo_doc",
            "page": 1,
            "spans": [
                {
                    "span_id": "p001_s001",
                    "text": "The request uses ELS_Command FLOGI.",
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
        },
    )
    _write_text(doc_root / "tables" / "table_0001" / "crop.png", "fake table crop")
    _write_jsonl(
        doc_root / "tables" / "table_0001" / "cells.jsonl",
        [
            {
                "cell_id": "r1c1",
                "row": 1,
                "col": 1,
                "text": "FLOGI",
                "page": 1,
                "bbox": [90, 80, 130, 100],
            }
        ],
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_claim_bundle_reverifies_and_writes_ir_input(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_fixture(tmp_path)

    reading_a = tmp_path / "readings" / "request"
    reading_b = tmp_path / "readings" / "payload"
    _write_jsonl(
        reading_a / "claims.jsonl",
        [
            {
                "claim_id": "request_command",
                "unit_id": "request",
                "doc_id": "demo_doc",
                "text": "The request uses ELS_Command FLOGI.",
                "kind": "field_presence",
                "evidence_refs": [
                    {
                        "type": "text_span",
                        "span_id": "p001_s001",
                        "quote": "ELS_Command FLOGI",
                    }
                ],
            }
        ],
    )
    _write_json(reading_a / "unresolved.json", {"items": []})
    _write_jsonl(
        reading_b / "claims.jsonl",
        [
            {
                "claim_id": "payload_command",
                "unit_id": "payload",
                "doc_id": "demo_doc",
                "text": "The payload table contains FLOGI.",
                "kind": "field_presence",
                "evidence_refs": [
                    {
                        "type": "table_cell",
                        "asset_id": "table_0001",
                        "cell_id": "r1c1",
                        "quote": "FLOGI",
                    }
                ],
            },
            {
                "claim_id": "bad_span",
                "unit_id": "payload",
                "doc_id": "demo_doc",
                "text": "This claim cites a missing span.",
                "kind": "other",
                "evidence_refs": [
                    {
                        "type": "text_span",
                        "span_id": "missing_span",
                        "quote": "missing",
                    }
                ],
            },
        ],
    )
    _write_json(reading_b / "unresolved.json", {"items": [{"claim_id": "needs_more"}]})

    from src.reading.bundle import build_claim_bundle

    result = build_claim_bundle(
        reading_dirs=[reading_a, reading_b],
        output_dir=tmp_path / "bundles" / "flogi",
        doc_id="demo_doc",
    )

    assert result["accepted_count"] == 2
    assert result["invalid_count"] == 1
    assert result["unresolved_count"] == 1
    claims = _read_jsonl(tmp_path / "bundles" / "flogi" / "claims_bundle.jsonl")
    assert [claim["claim_id"] for claim in claims] == ["request_command", "payload_command"]
    assert {claim["doc_id"] for claim in claims} == {"demo_doc"}
    assert claims[0]["source_doc_id"] == "demo_doc"
    assert claims[0]["source_reading"] == str(reading_a)
    assert all(claim["evidence_refs"] for claim in claims)
    evidence_map = json.loads((tmp_path / "bundles" / "flogi" / "evidence_map.json").read_text())
    assert sorted(evidence_map) == ["payload_command", "request_command"]
    report = json.loads((tmp_path / "bundles" / "flogi" / "verify_report.json").read_text())
    assert report["accepted_count"] == 2
    assert report["invalid"][0]["claim_id"] == "bad_span"


def test_reading_bundle_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_fixture(tmp_path)
    reading = tmp_path / "readings" / "request"
    _write_jsonl(
        reading / "claims.jsonl",
        [
            {
                "claim_id": "request_command",
                "unit_id": "request",
                "doc_id": "demo_doc",
                "text": "The request uses ELS_Command FLOGI.",
                "kind": "field_presence",
                "evidence_refs": [
                    {
                        "type": "text_span",
                        "span_id": "p001_s001",
                        "quote": "ELS_Command FLOGI",
                    }
                ],
            }
        ],
    )

    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.reading.bundle",
            "--reading",
            str(reading),
            "--out",
            str(tmp_path / "bundle"),
            "--doc-id",
            "demo_doc",
        ],
        cwd=tmp_path,
        env={"PYTHONPATH": str(repo_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "accepted_count" in completed.stdout
    claims = _read_jsonl(tmp_path / "bundle" / "claims_bundle.jsonl")
    assert len(claims) == 1
