"""Score reading outputs against a fixture-owned coverage checklist.

The checklist owns protocol-specific facts and page expectations. This module
only performs mechanical matching over answer text, citations, and retrieved
pages.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from src.agent.citation import extract_citations


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_page_specs(raw: Any) -> set[int]:
    pages: set[int] = set()
    if raw is None:
        return pages
    values = raw if isinstance(raw, list) else [raw]
    for value in values:
        if isinstance(value, int):
            pages.add(value)
            continue
        text = str(value).strip()
        if not text:
            continue
        for token in text.split(","):
            part = token.strip()
            if not part:
                continue
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start = int(start_text.strip())
                end = int(end_text.strip())
                if end < start:
                    start, end = end, start
                pages.update(range(start, end + 1))
            else:
                pages.add(int(part))
    return pages


def _match_pattern(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is not None


def _match_group(text: str, group: dict[str, Any]) -> tuple[bool, str | None]:
    label = str(group.get("label") or "unnamed")
    patterns = group.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        return False, label
    for pattern in patterns:
        if isinstance(pattern, str) and _match_pattern(text, pattern):
            return True, None
    return False, label


def _target_text(run_payload: dict[str, Any]) -> str:
    for key in ("answer_clean", "answer", "reading_md"):
        value = run_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _target_cite_pages(run_payload: dict[str, Any]) -> list[int]:
    citations = run_payload.get("citations")
    pages: list[int] = []
    if isinstance(citations, list):
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            try:
                pages.append(int(citation.get("page")))
            except (TypeError, ValueError):
                continue
    if pages:
        return sorted(set(pages))

    answer = run_payload.get("answer")
    if isinstance(answer, str):
        return sorted({citation.page for citation in extract_citations(answer)})
    return []


def _target_retrieved_pages(run_payload: dict[str, Any]) -> list[int]:
    pages: set[int] = set()
    for key in ("pages_retrieved", "all_pages_requested"):
        raw_pages = run_payload.get(key)
        if not isinstance(raw_pages, list):
            continue
        for page in raw_pages:
            try:
                pages.add(int(page))
            except (TypeError, ValueError):
                continue
    return sorted(pages)


def score_checklist(checklist: dict[str, Any], run_payload: dict[str, Any]) -> dict[str, Any]:
    """Return mechanical coverage/citation scores for a run payload."""
    text = _target_text(run_payload)
    cite_pages = set(_target_cite_pages(run_payload))
    retrieved_pages = set(_target_retrieved_pages(run_payload))
    raw_items = checklist.get("items")
    items = raw_items if isinstance(raw_items, list) else []

    scored_items: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or f"item_{len(scored_items) + 1:04d}")
        category = str(item.get("category") or "uncategorized")
        expected_pages = _parse_page_specs(item.get("expected_cite_pages"))
        required_groups = item.get("must_any")
        groups = required_groups if isinstance(required_groups, list) else []

        missing_groups: list[str] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            matched, missing = _match_group(text, group)
            if not matched and missing is not None:
                missing_groups.append(missing)

        coverage_pass = not missing_groups
        cite_page_pass = True if not expected_pages else bool(cite_pages & expected_pages)
        retrieved_page_pass = True if not expected_pages else bool(retrieved_pages & expected_pages)
        passed = coverage_pass and cite_page_pass and retrieved_page_pass

        category_stats = by_category.setdefault(category, {"passed": 0, "total": 0})
        category_stats["total"] += 1
        if passed:
            category_stats["passed"] += 1

        scored_items.append(
            {
                "id": item_id,
                "category": category,
                "description": item.get("description", ""),
                "status": "passed" if passed else "failed",
                "coverage_pass": coverage_pass,
                "cite_page_pass": cite_page_pass,
                "retrieved_page_pass": retrieved_page_pass,
                "missing_groups": missing_groups,
                "expected_cite_pages": sorted(expected_pages),
                "matched_cite_pages": sorted(cite_pages & expected_pages),
                "matched_retrieved_pages": sorted(retrieved_pages & expected_pages),
            }
        )

    passed_count = sum(1 for item in scored_items if item["status"] == "passed")
    total = len(scored_items)
    score = passed_count / total if total else 0.0
    return {
        "checklist_id": checklist.get("id"),
        "checklist_title": checklist.get("title"),
        "status": "passed" if total and passed_count == total else "failed",
        "score": round(score, 4),
        "passed_count": passed_count,
        "total_count": total,
        "by_category": by_category,
        "cite_pages": sorted(cite_pages),
        "retrieved_pages": sorted(retrieved_pages),
        "items": scored_items,
    }


def score_checklist_files(checklist_path: str | Path, run_path: str | Path) -> dict[str, Any]:
    return score_checklist(_read_json(Path(checklist_path)), _read_json(Path(run_path)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a live reading run against a coverage checklist.")
    parser.add_argument("--checklist", required=True, help="Checklist JSON path.")
    parser.add_argument("--run", required=True, help="Agent run JSON path.")
    parser.add_argument("--out", default=None, help="Optional report JSON output path.")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit non-zero when score is below this threshold, e.g. 1.0 for all pass.",
    )
    args = parser.parse_args(argv)

    report = score_checklist_files(args.checklist, args.run)
    if args.out:
        _write_json(Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_under is not None and float(report["score"]) < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

