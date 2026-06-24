from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_score_checklist_checks_text_cites_and_retrieved_pages():
    from src.evaluation.checklist import score_checklist

    checklist = {
        "id": "demo",
        "items": [
            {
                "id": "alpha",
                "category": "demo",
                "description": "Alpha must be covered from page 2.",
                "expected_cite_pages": [2],
                "must_any": [
                    {"label": "alpha", "patterns": ["Alpha"]},
                    {"label": "beta or gamma", "patterns": ["Beta", "Gamma"]},
                ],
            },
            {
                "id": "wrong_page",
                "category": "demo",
                "description": "Covered text but wrong cited page.",
                "expected_cite_pages": [4],
                "must_any": [{"label": "alpha", "patterns": ["Alpha"]}],
            },
        ],
    }
    run_payload = {
        "answer": "Alpha and Beta are present.<cite doc=\"demo.pdf\" page=\"2\"/>",
        "pages_retrieved": [2],
    }

    report = score_checklist(checklist, run_payload)

    assert report["score"] == 0.5
    assert report["passed_count"] == 1
    assert report["items"][0]["status"] == "passed"
    assert report["items"][1]["status"] == "failed"
    assert report["items"][1]["cite_page_pass"] is False


def test_score_checklist_cli_writes_report_and_honors_fail_under(tmp_path: Path):
    checklist_path = tmp_path / "checklist.json"
    run_path = tmp_path / "run.json"
    out_path = tmp_path / "report.json"
    _write_json(
        checklist_path,
        {
            "id": "demo",
            "items": [
                {
                    "id": "alpha",
                    "expected_cite_pages": [2],
                    "must_any": [{"label": "alpha", "patterns": ["Alpha"]}],
                }
            ],
        },
    )
    _write_json(
        run_path,
        {
            "answer": "Alpha is cited.<cite doc=\"demo.pdf\" page=\"2\"/>",
            "pages_retrieved": [2],
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.evaluation.checklist",
            "--checklist",
            str(checklist_path),
            "--run",
            str(run_path),
            "--out",
            str(out_path),
            "--fail-under",
            "1.0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(out_path.read_text(encoding="utf-8"))["score"] == 1.0

