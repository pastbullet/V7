"""Run focused reading tasks from a materialized reading plan."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from src.reading.runner import run_reading_claim_agent


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_list(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "[]"
    return json.dumps(value, ensure_ascii=False)


def _build_reading_goal_from_task(task_input: dict[str, Any]) -> tuple[str, str, str]:
    doc_id = str(task_input.get("doc_id") or "").strip()
    unit = task_input.get("unit") if isinstance(task_input.get("unit"), dict) else {}
    task = task_input.get("task") if isinstance(task_input.get("task"), dict) else {}
    unit_id = str(unit.get("unit_id") or "unit").strip()
    task_id = str(task.get("task_id") or "task").strip()
    goal = (
        f"Read focused task `{task_id}` for discovered unit `{unit_id}`.\n"
        f"Unit title: {unit.get('title') or unit_id}\n"
        f"Unit kind: {unit.get('kind') or 'protocol_unit'}\n"
        f"Task title: {task.get('title') or task_id}\n"
        f"Task type: {task.get('task_type') or 'focused_reading'}\n"
        f"Focused reading goal: {task.get('reading_goal') or ''}\n"
        f"Target outputs: {_format_list(task.get('target_outputs'))}\n"
        f"Candidate page ranges: {_format_list(task.get('page_ranges'))}\n"
        f"Required assets: {_format_list(task.get('must_include_assets'))}\n"
        f"Expected evidence types: {_format_list(task.get('expected_evidence_types'))}\n"
        f"Completion criteria: {_format_list(task.get('completion_criteria'))}\n\n"
        "Only produce claims for this focused task. If a required fact is outside the "
        "candidate ranges/assets, fetch the missing relevant evidence and include it; "
        "do not silently omit required branches, fields, conditions, or cross-references."
    )
    return doc_id, f"{unit_id}__{task_id}", goal


async def run_readings_from_plan(
    *,
    plan_path: str | Path,
    output_dir: str | Path | None = None,
    model: str | None = None,
    max_turns: int = 25,
) -> dict[str, Any]:
    """Run the claim reader for every task in ``reading_plan.json``."""
    plan_file = Path(plan_path)
    plan = _read_json(plan_file)
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        tasks = []

    base_out = Path(output_dir) if output_dir is not None else plan_file.parent
    base_out.mkdir(parents=True, exist_ok=True)

    manifest_tasks: list[dict[str, Any]] = []
    totals = {
        "accepted_claim_count": 0,
        "unresolved_count": 0,
        "invalid_count": 0,
        "failed_count": 0,
        "llm_turns": 0,
    }

    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_input_path = task.get("task_input_path")
        if not isinstance(task_input_path, str) or not task_input_path:
            continue
        task_input = _read_json(Path(task_input_path))
        doc_id, task_unit_id, reading_goal = _build_reading_goal_from_task(task_input)
        if not doc_id:
            raise ValueError(f"Task input is missing doc_id: {task_input_path}")

        task_dir = Path(task.get("task_dir") or Path(task_input_path).parent)
        reading_dir = task_dir / "reading"
        try:
            result = await run_reading_claim_agent(
                doc_name=doc_id,
                unit_id=task_unit_id,
                reading_goal=reading_goal,
                output_dir=reading_dir,
                model=model,
                max_turns=max_turns,
            )
        except Exception as exc:  # noqa: BLE001
            reading_dir.mkdir(parents=True, exist_ok=True)
            error_payload = {
                "task_id": task.get("task_id"),
                "task_unit_id": task_unit_id,
                "task_input_path": task_input_path,
                "error": str(exc),
            }
            _write_json(reading_dir / "task_error.json", error_payload)
            totals["failed_count"] += 1
            manifest_tasks.append(
                {
                    "task_id": task.get("task_id"),
                    "task_unit_id": task_unit_id,
                    "task_input_path": task_input_path,
                    "reading_dir": str(reading_dir),
                    "status": "failed",
                    "error": str(exc),
                    "accepted_count": 0,
                    "unresolved_count": 0,
                    "invalid_count": 0,
                    "llm_turns": 0,
                }
            )
            continue

        accepted = int(result.get("accepted_count", 0) or 0)
        unresolved = int(result.get("unresolved_count", 0) or 0)
        invalid = int(result.get("invalid_count", 0) or 0)
        turns = int(result.get("llm_turns", 0) or 0)
        totals["accepted_claim_count"] += accepted
        totals["unresolved_count"] += unresolved
        totals["invalid_count"] += invalid
        totals["llm_turns"] += turns
        manifest_tasks.append(
            {
                "task_id": task.get("task_id"),
                "task_unit_id": task_unit_id,
                "task_input_path": task_input_path,
                "reading_dir": str(reading_dir),
                "status": "completed",
                "accepted_count": accepted,
                "unresolved_count": unresolved,
                "invalid_count": invalid,
                "llm_turns": turns,
            }
        )

    manifest = {
        "plan_path": str(plan_file),
        "doc_id": plan.get("doc_id"),
        "unit": plan.get("unit"),
        "task_count": len(manifest_tasks),
        "tasks": manifest_tasks,
        "totals": totals,
    }
    _write_json(base_out / "task_reading_manifest.json", manifest)

    return {
        "output_dir": str(base_out),
        "task_count": len(manifest_tasks),
        **totals,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SpecIndex readings from a reading plan.")
    parser.add_argument("--plan", required=True, help="Path to reading_plan.json.")
    parser.add_argument("--out", default=None, help="Optional output directory for task_reading_manifest.json.")
    parser.add_argument("--model", default=None, help="Optional LLM model name.")
    parser.add_argument("--max-turns", type=int, default=25)
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_readings_from_plan(
            plan_path=args.plan,
            output_dir=args.out,
            model=args.model,
            max_turns=args.max_turns,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
