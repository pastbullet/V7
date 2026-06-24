"""Materialize IR-oriented reading plans for discovered protocol units.

The planner layer is intentionally mechanical.  An LLM or user may propose
semantic task boundaries; this module only normalizes the proposal, checks the
shape of page ranges/assets/budgets, and writes auditable task inputs.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from src.tools.page_content import parse_pages
from src.tools.specindex_assets import get_image, get_table


ALLOWED_ASSET_TYPES = {"table", "figure", "image"}
DEFAULT_EVIDENCE_TYPES = ["text_span", "table_cell", "figure_crop", "figure_region"]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_dir_name(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "").strip())
    return safe.strip("._") or "task"


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _as_object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _normalize_unit(raw: dict[str, Any]) -> dict[str, Any]:
    unit_id = str(raw.get("unit_id") or "unit").strip()
    title = str(raw.get("title") or raw.get("name") or unit_id).strip()
    return {
        "unit_id": unit_id,
        "title": title,
        "kind": str(raw.get("kind") or raw.get("unit_type") or "protocol_unit").strip(),
        "target_ir": _as_string_list(raw.get("target_ir")),
        "source_anchors": _as_string_list(raw.get("source_anchors")),
        "dependencies": _as_string_list(raw.get("dependencies")),
        "priority": str(raw.get("priority") or "").strip(),
        "scope_status": str(raw.get("scope_status") or "in_scope").strip(),
        "notes": str(raw.get("notes") or "").strip(),
    }


def _normalize_asset(raw: dict[str, Any]) -> dict[str, str]:
    asset_id = str(raw.get("asset_id") or "").strip()
    asset_type = str(raw.get("type") or raw.get("asset_type") or "").strip()
    return {"type": asset_type, "asset_id": asset_id}


def _normalize_budget(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        raw = {}
    budget: dict[str, int] = {}
    for key in ("max_pages", "max_tables", "max_figures", "max_tool_calls"):
        value = raw.get(key)
        if value is None or value == "":
            continue
        budget[key] = int(value)
    return budget


def _normalize_task(raw: dict[str, Any], index: int) -> dict[str, Any]:
    task_id = str(raw.get("task_id") or f"task_{index:04d}").strip()
    title = str(raw.get("title") or task_id).strip()
    page_ranges = (
        _as_string_list(raw.get("page_ranges"))
        or _as_string_list(raw.get("candidate_pages"))
        or _as_string_list(raw.get("pages"))
    )
    assets = [_normalize_asset(item) for item in _as_object_list(raw.get("must_include_assets"))]
    return {
        "task_id": task_id,
        "title": title,
        "task_type": str(raw.get("task_type") or "focused_reading").strip(),
        "target_outputs": _as_string_list(raw.get("target_outputs")),
        "reading_goal": str(raw.get("reading_goal") or raw.get("goal") or "").strip(),
        "page_ranges": page_ranges,
        "must_include_assets": assets,
        "expected_evidence_types": _as_string_list(raw.get("expected_evidence_types")) or list(DEFAULT_EVIDENCE_TYPES),
        "completion_criteria": _as_string_list(raw.get("completion_criteria")),
        "dependencies": _as_string_list(raw.get("dependencies")),
        "budget": _normalize_budget(raw.get("budget")),
        "status": str(raw.get("status") or "accepted").strip(),
        "reason": str(raw.get("reason") or "").strip(),
    }


def _validate_page_ranges(page_ranges: list[str]) -> list[str]:
    errors: list[str] = []
    for page_range in page_ranges:
        try:
            parse_pages(page_range)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"invalid page range {page_range!r}: {exc}")
    return errors


def _validate_assets(doc_id: str, assets: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for asset in assets:
        asset_id = asset.get("asset_id", "")
        asset_type = asset.get("type", "")
        if not asset_id:
            errors.append("asset is missing asset_id")
            continue
        if asset_type not in ALLOWED_ASSET_TYPES:
            errors.append(f"asset {asset_id} has unsupported type {asset_type!r}")
            continue
        normalized_type = "figure" if asset_type == "image" else asset_type
        result = (
            get_table(asset_id, doc_id=doc_id)
            if normalized_type == "table"
            else get_image(asset_id, doc_id=doc_id)
        )
        if "error" in result:
            errors.append(f"asset {asset_id} not found: {result['error']}")
    return errors


def _validate_budget(budget: dict[str, int]) -> list[str]:
    errors: list[str] = []
    for key, value in budget.items():
        if value < 0:
            errors.append(f"budget {key} must be non-negative")
        if key in {"max_pages", "max_tool_calls"} and value == 0:
            errors.append(f"budget {key} must be positive")
    return errors


def _task_input(unit: dict[str, Any], task: dict[str, Any], doc_id: str) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "unit": unit,
        "task": task,
    }


def materialize_reading_plan(
    *,
    doc_id: str,
    unit: dict[str, Any],
    task_candidates: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write a reading plan and per-task inputs after structural validation.

    The function does not infer protocol semantics.  It accepts proposed task
    boundaries and only verifies that the plan is executable and auditable.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    normalized_unit = _normalize_unit(unit if isinstance(unit, dict) else {})
    _write_json(out / "unit_meta.json", {"doc_id": doc_id, **normalized_unit})

    accepted_tasks: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()

    for index, raw_task in enumerate(task_candidates, start=1):
        if not isinstance(raw_task, dict):
            continue
        task = _normalize_task(raw_task, index)
        task_id = task["task_id"]

        if task["status"] == "unresolved":
            unresolved.append({**task, "reason": task["reason"] or "unresolved"})
            continue

        errors: list[str] = []
        if not task_id:
            errors.append("missing task_id")
        if task_id in seen_task_ids:
            errors.append(f"duplicate task_id {task_id}")
        if not task["reading_goal"]:
            errors.append("missing reading_goal")
        if not task["target_outputs"]:
            errors.append("missing target_outputs")
        errors.extend(_validate_page_ranges(task["page_ranges"]))
        errors.extend(_validate_assets(doc_id, task["must_include_assets"]))
        errors.extend(_validate_budget(task["budget"]))

        if errors:
            invalid.append({**task, "errors": errors})
            continue

        seen_task_ids.add(task_id)
        task_dir = out / "tasks" / safe_dir_name(task_id)
        task_input_path = task_dir / "task_input.json"
        task_with_path = {
            **task,
            "task_dir": str(task_dir),
            "task_input_path": str(task_input_path),
        }
        _write_json(task_input_path, _task_input(normalized_unit, task_with_path, doc_id))
        accepted_tasks.append(task_with_path)

    reading_plan = {
        "doc_id": doc_id,
        "unit": normalized_unit,
        "task_count": len(accepted_tasks),
        "tasks": accepted_tasks,
    }
    verify_report = {
        "doc_id": doc_id,
        "unit_id": normalized_unit["unit_id"],
        "accepted_count": len(accepted_tasks),
        "unresolved_count": len(unresolved),
        "invalid_count": len(invalid),
        "accepted": [{"task_id": task["task_id"], "task_input_path": task["task_input_path"]} for task in accepted_tasks],
        "unresolved": unresolved,
        "invalid": invalid,
    }

    _write_json(out / "reading_plan.json", reading_plan)
    _write_json(out / "unresolved.json", {"items": unresolved})
    _write_json(out / "verify_report.json", verify_report)

    return {
        "output_dir": str(out),
        "accepted_count": len(accepted_tasks),
        "unresolved_count": len(unresolved),
        "invalid_count": len(invalid),
    }


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Reading plan input must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a SpecIndex reading plan.")
    parser.add_argument("--input", required=True, help="JSON payload with doc_id, unit, and task_candidates/tasks.")
    parser.add_argument("--out", required=True, help="Output directory for unit_meta.json, reading_plan.json, and task inputs.")
    args = parser.parse_args(argv)

    payload = _load_payload(Path(args.input))
    tasks = payload.get("task_candidates")
    if not isinstance(tasks, list):
        tasks = payload.get("tasks")
    result = materialize_reading_plan(
        doc_id=str(payload["doc_id"]),
        unit=payload.get("unit") if isinstance(payload.get("unit"), dict) else {},
        task_candidates=tasks if isinstance(tasks, list) else [],
        output_dir=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
