from __future__ import annotations

import asyncio
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


def _build_asset_fixture(root: Path) -> None:
    doc_root = root / "processed_specs" / "demo" / "demo_doc"
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
            "source_crop": "crop.png",
        },
    )
    _write_text(doc_root / "tables" / "table_0001" / "crop.png", "fake crop")
    _write_jsonl(
        doc_root / "tables" / "table_0001" / "cells.jsonl",
        [{"cell_id": "r1c1", "text": "Field", "page": 1}],
    )


def test_materialize_reading_plan_writes_task_inputs_and_reports(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_asset_fixture(tmp_path)

    from src.reading.planner import materialize_reading_plan

    output_dir = tmp_path / "reading" / "units" / "demo_unit"
    result = materialize_reading_plan(
        doc_id="demo_doc",
        unit={
            "unit_id": "demo_unit",
            "title": "Demo Unit",
            "kind": "message_structure",
            "target_ir": ["MessageIR"],
            "source_anchors": ["sec_1"],
        },
        task_candidates=[
            {
                "task_id": "fixed_fields",
                "title": "Fixed fields",
                "task_type": "message_format",
                "target_outputs": ["fields", "evidence"],
                "reading_goal": "Read fixed fields and produce grounded claims.",
                "page_ranges": ["1-2"],
                "must_include_assets": [{"type": "table", "asset_id": "table_0001"}],
                "completion_criteria": ["Every field has evidence."],
                "budget": {"max_pages": 2, "max_tables": 1, "max_tool_calls": 6},
            },
            {
                "task_id": "later",
                "status": "unresolved",
                "reason": "Needs later scope decision.",
            },
            {
                "task_id": "text_only_flow",
                "target_outputs": ["branches"],
                "reading_goal": "Read text-only flow branches.",
                "page_ranges": ["2"],
                "budget": {"max_pages": 1, "max_tables": 0, "max_tool_calls": 4},
            },
            {
                "task_id": "bad_range",
                "target_outputs": ["fields"],
                "reading_goal": "Read bad range.",
                "page_ranges": ["4-2"],
            },
            {
                "task_id": "bad_asset",
                "target_outputs": ["fields"],
                "reading_goal": "Read bad asset.",
                "must_include_assets": [{"type": "table", "asset_id": "missing"}],
            },
        ],
        output_dir=output_dir,
    )

    assert result == {
        "output_dir": str(output_dir),
        "accepted_count": 2,
        "unresolved_count": 1,
        "invalid_count": 2,
    }
    plan = json.loads((output_dir / "reading_plan.json").read_text(encoding="utf-8"))
    assert plan["unit"]["unit_id"] == "demo_unit"
    assert [task["task_id"] for task in plan["tasks"]] == ["fixed_fields", "text_only_flow"]
    task_input_path = Path(plan["tasks"][0]["task_input_path"])
    task_input = json.loads(task_input_path.read_text(encoding="utf-8"))
    assert task_input["doc_id"] == "demo_doc"
    assert task_input["unit"]["target_ir"] == ["MessageIR"]
    assert task_input["task"]["page_ranges"] == ["1-2"]
    assert task_input["task"]["must_include_assets"] == [{"type": "table", "asset_id": "table_0001"}]
    report = json.loads((output_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert report["accepted_count"] == 2
    assert report["unresolved"][0]["task_id"] == "later"
    assert {item["task_id"] for item in report["invalid"]} == {"bad_range", "bad_asset"}


def test_run_readings_from_plan_calls_reader_once_per_task(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_asset_fixture(tmp_path)

    from src.reading.planner import materialize_reading_plan
    from src.reading import from_plan

    plan_dir = tmp_path / "reading" / "units" / "demo_unit"
    materialize_reading_plan(
        doc_id="demo_doc",
        unit={"unit_id": "demo_unit", "title": "Demo Unit", "kind": "message_structure"},
        task_candidates=[
            {
                "task_id": "fixed_fields",
                "target_outputs": ["fields"],
                "reading_goal": "Read fixed fields.",
                "page_ranges": ["1"],
                "must_include_assets": [{"type": "table", "asset_id": "table_0001"}],
            }
        ],
        output_dir=plan_dir,
    )

    calls: list[dict] = []

    async def fake_run_reading_claim_agent(**kwargs):
        calls.append(kwargs)
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        return {
            "output_dir": str(out),
            "accepted_count": 2,
            "unresolved_count": 0,
            "invalid_count": 0,
            "llm_turns": 4,
        }

    monkeypatch.setattr(from_plan, "run_reading_claim_agent", fake_run_reading_claim_agent)

    result = asyncio.run(from_plan.run_readings_from_plan(plan_path=plan_dir / "reading_plan.json"))

    assert result["task_count"] == 1
    assert result["accepted_claim_count"] == 2
    assert calls[0]["doc_name"] == "demo_doc"
    assert calls[0]["unit_id"] == "demo_unit__fixed_fields"
    assert calls[0]["output_dir"] == plan_dir / "tasks" / "fixed_fields" / "reading"
    assert "Read fixed fields." in calls[0]["reading_goal"]
    assert "Candidate page ranges" in calls[0]["reading_goal"]
    assert "table_0001" in calls[0]["reading_goal"]
    manifest = json.loads((plan_dir / "task_reading_manifest.json").read_text(encoding="utf-8"))
    assert manifest["totals"]["llm_turns"] == 4


def test_run_readings_from_plan_records_task_failure(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_asset_fixture(tmp_path)

    from src.reading.planner import materialize_reading_plan
    from src.reading import from_plan

    plan_dir = tmp_path / "reading" / "units" / "demo_unit"
    materialize_reading_plan(
        doc_id="demo_doc",
        unit={"unit_id": "demo_unit", "title": "Demo Unit", "kind": "message_structure"},
        task_candidates=[
            {
                "task_id": "fixed_fields",
                "target_outputs": ["fields"],
                "reading_goal": "Read fixed fields.",
                "page_ranges": ["1"],
                "must_include_assets": [{"type": "table", "asset_id": "table_0001"}],
            }
        ],
        output_dir=plan_dir,
    )

    async def fake_run_reading_claim_agent(**kwargs):
        raise ValueError("bad json")

    monkeypatch.setattr(from_plan, "run_reading_claim_agent", fake_run_reading_claim_agent)

    result = asyncio.run(from_plan.run_readings_from_plan(plan_path=plan_dir / "reading_plan.json"))

    assert result["task_count"] == 1
    assert result["failed_count"] == 1
    error_path = plan_dir / "tasks" / "fixed_fields" / "reading" / "task_error.json"
    error_payload = json.loads(error_path.read_text(encoding="utf-8"))
    assert error_payload["task_id"] == "fixed_fields"
    assert "bad json" in error_payload["error"]
    manifest = json.loads((plan_dir / "task_reading_manifest.json").read_text(encoding="utf-8"))
    assert manifest["tasks"][0]["status"] == "failed"


def test_reading_planner_cli_help():
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-m", "src.reading.planner", "--help"],
        cwd=repo_root,
        env={"PYTHONPATH": str(repo_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--input" in completed.stdout
    assert "--out" in completed.stdout


def test_reading_from_plan_cli_help():
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-m", "src.reading.from_plan", "--help"],
        cwd=repo_root,
        env={"PYTHONPATH": str(repo_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--plan" in completed.stdout
    assert "--max-turns" in completed.stdout
