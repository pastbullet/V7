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


def _build_acceptance_fixture(root: Path) -> dict[str, Path]:
    doc_root = root / "processed_specs" / "local" / "demo_doc"
    for page in (1, 2):
        _write_text(doc_root / "pages" / f"page_{page:03d}" / "page.png", "fake page image")
        _write_json(
            doc_root / "pages" / f"page_{page:03d}" / "text.json",
            {
                "doc_id": "demo_doc",
                "page": page,
                "spans": [
                    {
                        "span_id": f"p{page:03d}_s001",
                        "text": f"Unit Alpha evidence on page {page}.",
                        "bbox": [10, 20, 300, 40],
                    }
                ],
                "asset_ids": ["table_0001"] if page == 1 else ["figure_0001"],
            },
        )

    _write_text(
        doc_root / "assets" / "assets_manifest.jsonl",
        json.dumps(
            {
                "asset_id": "table_0001",
                "type": "table",
                "caption": "Table 1 Alpha Payload",
                "pages": [1, 2],
                "bbox": [10, 60, 300, 160],
                "path": "tables/table_0001/table_meta.json",
                "logical_table": True,
                "fragment_ids": ["table_0001_frag_a", "table_0001_frag_b"],
            }
        )
        + "\n"
        + json.dumps(
            {
                "asset_id": "figure_0001",
                "type": "figure",
                "caption": "Figure 1 Alpha Flow",
                "pages": [2],
                "bbox": [20, 200, 280, 360],
                "path": "figures/figure_0001/figure_meta.json",
            }
        )
        + "\n",
    )
    _write_json(
        doc_root / "tables" / "table_0001" / "table_meta.json",
        {
            "asset_id": "table_0001",
            "caption": "Table 1 Alpha Payload",
            "pages": [1, 2],
            "bbox": [10, 60, 300, 160],
            "source_crop": "crop.png",
            "logical_table": True,
            "fragment_ids": ["table_0001_frag_a", "table_0001_frag_b"],
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
                "text": "Alpha Field",
                "page": 1,
                "bbox": [10, 70, 80, 90],
            },
            {
                "cell_id": "r2c1",
                "row": 2,
                "col": 1,
                "text": "Variable Tail",
                "page": 2,
                "bbox": [10, 70, 90, 90],
            },
        ],
    )
    _write_json(
        doc_root / "figures" / "figure_0001" / "figure_meta.json",
        {
            "asset_id": "figure_0001",
            "caption": "Figure 1 Alpha Flow",
            "page": 2,
            "pages": [2],
            "bbox": [20, 200, 280, 360],
            "source_crop": "crop.png",
            "vision_summary_file": "vision_summary.json",
        },
    )
    _write_text(doc_root / "figures" / "figure_0001" / "crop.png", "fake figure crop")
    _write_json(doc_root / "figures" / "figure_0001" / "vision_summary.json", {"derived": True})

    reading_dir = root / "readings" / "alpha"
    _write_text(reading_dir / "reading.md", "# Alpha\n\nReadable unit explanation.")
    _write_jsonl(
        reading_dir / "claims.jsonl",
        [
            {
                "claim_id": "alpha_span",
                "unit_id": "alpha",
                "doc_id": "demo_doc",
                "text": "Unit Alpha evidence is present.",
                "kind": "other",
                "evidence_refs": [
                    {"type": "text_span", "span_id": "p001_s001", "quote": "Unit Alpha"}
                ],
            }
        ],
    )
    _write_json(reading_dir / "verify_report.json", {"accepted_count": 1, "unresolved_count": 0, "invalid_count": 0})
    _write_json(reading_dir / "unresolved.json", {"items": []})

    discovery_dir = root / "discoveries" / "alpha"
    _write_text(discovery_dir / "discovery.md", "Discovered Alpha.")
    _write_json(discovery_dir / "verify_report.json", {"accepted_count": 1, "unresolved_count": 0, "invalid_count": 0})
    _write_json(
        discovery_dir / "discovered_units.json",
        {"doc_id": "demo_doc", "units": [{"unit_id": "alpha", "title": "Alpha"}]},
    )

    bundle_dir = root / "bundles" / "alpha"
    bundle_claims = [
        {
            "claim_id": "alpha_span",
            "unit_id": "alpha",
            "doc_id": "demo_doc",
            "text": "Unit Alpha evidence is present.",
            "kind": "other",
            "evidence_refs": [
                {"type": "text_span", "span_id": "p001_s001", "quote": "Unit Alpha"}
            ],
            "source_reading": str(reading_dir),
        },
        {
            "claim_id": "alpha_table",
            "unit_id": "alpha",
            "doc_id": "demo_doc",
            "text": "Alpha Field appears in the payload table.",
            "kind": "field_presence",
            "evidence_refs": [
                {
                    "type": "table_cell",
                    "asset_id": "table_0001",
                    "cell_id": "r1c1",
                    "quote": "Alpha Field",
                }
            ],
            "source_reading": str(reading_dir),
        },
        {
            "claim_id": "alpha_figure",
            "unit_id": "alpha",
            "doc_id": "demo_doc",
            "text": "The Alpha flow has a figure crop.",
            "kind": "other",
            "evidence_refs": [{"type": "figure_crop", "asset_id": "figure_0001"}],
            "source_reading": str(reading_dir),
        },
    ]
    _write_jsonl(bundle_dir / "claims_bundle.jsonl", bundle_claims)
    _write_json(bundle_dir / "evidence_map.json", {row["claim_id"]: row["evidence_refs"] for row in bundle_claims})
    _write_json(bundle_dir / "unresolved.json", {"items": []})
    _write_json(
        bundle_dir / "verify_report.json",
        {
            "doc_id": "demo_doc",
            "accepted_count": 3,
            "unresolved_count": 0,
            "invalid_count": 0,
            "source_readings": [str(reading_dir)],
        },
    )

    return {
        "doc_root": doc_root,
        "reading_dir": reading_dir,
        "discovery_dir": discovery_dir,
        "bundle_dir": bundle_dir,
    }


def test_ir_before_acceptance_audit_passes_complete_fixture(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = _build_acceptance_fixture(tmp_path)

    from src.reading.acceptance import run_ir_before_acceptance_audit

    report = run_ir_before_acceptance_audit(
        doc_id="demo_doc",
        processed_doc_root=paths["doc_root"],
        bundle_dir=paths["bundle_dir"],
        reading_dirs=[paths["reading_dir"]],
        discovery_dirs=[paths["discovery_dir"]],
        coverage_terms=["Unit Alpha", "Alpha Field"],
        output_path=tmp_path / "audit.json",
    )

    assert report["status"] == "accepted"
    assert report["summary"]["failed"] == 0
    assert (tmp_path / "audit.json").exists()
    check_ids = {check["id"] for check in report["checks"]}
    assert "agent_prompt_tool_discipline" in check_ids
    assert "processed_page_assets" in check_ids
    assert "bundle_claim_evidence" in check_ids
    assert "coverage_terms" in check_ids


def test_ir_before_acceptance_audit_rejects_derived_or_unverified_refs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = _build_acceptance_fixture(tmp_path)
    bundle_path = paths["bundle_dir"] / "claims_bundle.jsonl"
    rows = [
        json.loads(line)
        for line in bundle_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[0]["evidence_refs"] = [{"type": "vision_summary", "asset_id": "figure_0001"}]
    _write_jsonl(bundle_path, rows)

    from src.reading.acceptance import run_ir_before_acceptance_audit

    report = run_ir_before_acceptance_audit(
        doc_id="demo_doc",
        processed_doc_root=paths["doc_root"],
        bundle_dir=paths["bundle_dir"],
        reading_dirs=[paths["reading_dir"]],
        discovery_dirs=[paths["discovery_dir"]],
    )

    assert report["status"] == "rejected"
    failures = {check["id"]: check for check in report["checks"] if check["status"] == "failed"}
    assert "bundle_claim_evidence" in failures
    assert "vision_summary" in json.dumps(failures["bundle_claim_evidence"], ensure_ascii=False)


def test_ir_before_acceptance_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = _build_acceptance_fixture(tmp_path)
    repo_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.reading.acceptance",
            "--doc-id",
            "demo_doc",
            "--processed-doc-root",
            str(paths["doc_root"]),
            "--bundle",
            str(paths["bundle_dir"]),
            "--reading",
            str(paths["reading_dir"]),
            "--discovery",
            str(paths["discovery_dir"]),
            "--coverage-term",
            "Unit Alpha",
            "--out",
            str(tmp_path / "audit.json"),
        ],
        cwd=tmp_path,
        env={"PYTHONPATH": str(repo_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "accepted" in completed.stdout
    report = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert report["status"] == "accepted"
