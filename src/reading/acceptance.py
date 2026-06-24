"""Mechanical acceptance audit for IR-before SpecIndex artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.tools.page_content import get_page_content
from src.tools.schemas import TOOL_SCHEMAS
from src.tools.specindex_assets import verify_evidence


RAW_EVIDENCE_TYPES = {"text_span", "table_cell", "figure_crop", "figure_region"}
FORBIDDEN_TOOL_NAMES = {"search_nodes", "get_prev_node", "get_next_node"}
REQUIRED_TOOL_NAMES = {
    "get_document_structure",
    "get_page_content",
    "list_assets",
    "get_table",
    "get_image",
    "verify_evidence",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return _read_json(path)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        item = json.loads(text)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _check(check_id: str, ok: bool, detail: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "passed" if ok else "failed",
        "detail": detail,
        "evidence": evidence or {},
    }


def _tool_names() -> set[str]:
    names: set[str] = set()
    for schema in TOOL_SCHEMAS:
        try:
            names.add(str(schema["function"]["name"]))
        except KeyError:
            continue
    return names


def _check_agent_prompt_tool_discipline(project_root: Path) -> dict[str, Any]:
    names = _tool_names()
    prompt_paths = [
        project_root / "src" / "agent" / "prompts" / "reading_claim_system.txt",
        project_root / "src" / "agent" / "prompts" / "unit_discovery_system.txt",
    ]
    prompt_text = "\n".join(_read_text(path) for path in prompt_paths if path.exists()).lower()
    missing_tools = sorted(REQUIRED_TOOL_NAMES - names)
    forbidden_tools = sorted(FORBIDDEN_TOOL_NAMES & names)
    required_prompt_terms = [
        "get_document_structure",
        "get_page_content",
        "list_assets",
        "get_table",
        "get_image",
        "verify_evidence",
        "reading.md",
        "vision_summary",
        "common knowledge",
    ]
    missing_prompt_terms = [term for term in required_prompt_terms if term.lower() not in prompt_text]
    ok = not missing_tools and not forbidden_tools and not missing_prompt_terms
    return _check(
        "agent_prompt_tool_discipline",
        ok,
        "Agent-visible tools and prompts enforce SpecIndex reading order and raw evidence discipline.",
        {
            "missing_tools": missing_tools,
            "forbidden_tools": forbidden_tools,
            "missing_prompt_terms": missing_prompt_terms,
            "prompt_paths": [str(path) for path in prompt_paths],
        },
    )


def _valid_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
    )


def _check_processed_page_assets(processed_doc_root: Path) -> dict[str, Any]:
    pages_dir = processed_doc_root / "pages"
    page_dirs = sorted(path for path in pages_dir.glob("page_*") if path.is_dir())
    missing: list[str] = []
    span_count = 0
    asset_ref_count = 0
    for page_dir in page_dirs:
        if not (page_dir / "page.png").exists():
            missing.append(str(page_dir / "page.png"))
        payload = _read_json_if_exists(page_dir / "text.json")
        if not isinstance(payload, dict):
            missing.append(str(page_dir / "text.json"))
            continue
        spans = payload.get("spans")
        if not isinstance(spans, list) or not spans:
            missing.append(f"{page_dir}/text.json:spans")
            continue
        for span in spans:
            if not isinstance(span, dict):
                missing.append(f"{page_dir}/text.json:non_object_span")
                continue
            if not span.get("span_id") or not isinstance(span.get("text"), str) or not _valid_bbox(span.get("bbox")):
                missing.append(f"{page_dir}/text.json:{span.get('span_id') or 'missing_span_id'}")
            else:
                span_count += 1
        asset_ids = payload.get("asset_ids")
        if isinstance(asset_ids, list):
            asset_ref_count += len(asset_ids)

    ok = bool(page_dirs) and not missing and span_count > 0
    return _check(
        "processed_page_assets",
        ok,
        "Processed pages have page images, span ids, span bboxes, text, and page asset refs.",
        {
            "page_count": len(page_dirs),
            "span_count": span_count,
            "asset_ref_count": asset_ref_count,
            "missing": missing[:25],
        },
    )


def _check_page_tool(doc_id: str) -> dict[str, Any]:
    page = get_page_content(doc_id, "1")
    content = page.get("content") if isinstance(page, dict) else None
    first = content[0] if isinstance(content, list) and content else {}
    ok = (
        isinstance(first, dict)
        and isinstance(first.get("text_spans"), list)
        and "asset_refs" in first
        and isinstance(first.get("metadata"), dict)
        and "page_image_path" in first
    )
    return _check(
        "page_span_tool_shape",
        ok,
        "get_page_content exposes text_spans, asset_refs, page image, and metadata.",
        {"keys": sorted(first.keys()) if isinstance(first, dict) else []},
    )


def _check_assets(processed_doc_root: Path) -> dict[str, Any]:
    assets = _read_jsonl(processed_doc_root / "assets" / "assets_manifest.jsonl")
    missing: list[str] = []
    table_count = 0
    figure_count = 0
    logical_tables = 0
    cell_count = 0
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("asset_id") or "")
        asset_type = asset.get("type")
        if not asset_id or asset_type not in {"table", "figure"}:
            missing.append(f"bad asset manifest row: {asset}")
            continue
        meta_path = processed_doc_root / str(asset.get("path") or "")
        if not meta_path.exists():
            missing.append(str(meta_path))
            continue
        meta = _read_json_if_exists(meta_path)
        if not isinstance(meta, dict):
            missing.append(f"{meta_path}:invalid_json")
            continue
        crop = meta_path.parent / str(meta.get("source_crop", "crop.png"))
        if not crop.exists():
            missing.append(str(crop))
        if not _valid_bbox(asset.get("bbox", meta.get("bbox"))):
            missing.append(f"{asset_id}:missing_bbox")
        if asset_type == "table":
            table_count += 1
            cells = _read_jsonl(meta_path.parent / "cells.jsonl")
            if bool(asset.get("logical_table") or meta.get("logical_table")) and len(asset.get("pages") or meta.get("pages") or []) > 1:
                logical_tables += 1
            for cell in cells:
                if not cell.get("cell_id") or not isinstance(cell.get("text"), str) or not _valid_bbox(cell.get("bbox")) or not cell.get("page"):
                    missing.append(f"{asset_id}:bad_cell:{cell.get('cell_id')}")
                else:
                    cell_count += 1
        if asset_type == "figure":
            figure_count += 1

    ok = bool(assets) and table_count > 0 and figure_count > 0 and logical_tables > 0 and cell_count > 0 and not missing
    return _check(
        "asset_logical_objects",
        ok,
        "Asset manifest exposes table/figure objects; tables have stable cells; at least one cross-page logical table is recorded.",
        {
            "asset_count": len(assets),
            "table_count": table_count,
            "figure_count": figure_count,
            "logical_table_count": logical_tables,
            "cell_count": cell_count,
            "missing": missing[:25],
        },
    )


def _check_reports(label: str, dirs: list[Path]) -> dict[str, Any]:
    bad: list[str] = []
    accepted_total = 0
    for directory in dirs:
        report = _read_json_if_exists(directory / "verify_report.json")
        if not isinstance(report, dict):
            bad.append(f"{directory}:missing_verify_report")
            continue
        accepted_total += int(report.get("accepted_count") or 0)
        if int(report.get("invalid_count") or 0) != 0:
            bad.append(f"{directory}:invalid_count={report.get('invalid_count')}")
        if not (directory / ("reading.md" if label == "reading_reports" else "discovery.md")).exists() and label != "bundle_report":
            bad.append(f"{directory}:missing_markdown")
    return _check(
        label,
        not bad and accepted_total > 0,
        f"{label} have verify reports with accepted evidence and no invalid refs.",
        {"accepted_total": accepted_total, "bad": bad},
    )


def _check_bundle_claim_evidence(doc_id: str, bundle_dir: Path) -> dict[str, Any]:
    claims = _read_jsonl(bundle_dir / "claims_bundle.jsonl")
    report = _read_json_if_exists(bundle_dir / "verify_report.json")
    bad: list[dict[str, Any]] = []
    evidence_type_counts: dict[str, int] = {}
    for claim in claims:
        refs = claim.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            bad.append({"claim_id": claim.get("claim_id"), "reason": "missing_raw_evidence"})
            continue
        for ref in refs:
            ref_type = ref.get("type") if isinstance(ref, dict) else None
            evidence_type_counts[str(ref_type)] = evidence_type_counts.get(str(ref_type), 0) + 1
            if ref_type not in RAW_EVIDENCE_TYPES:
                bad.append({"claim_id": claim.get("claim_id"), "reason": f"{ref_type} is not raw evidence", "ref": ref})
        verification = verify_evidence(
            doc_id=doc_id,
            claim=str(claim.get("text") or ""),
            evidence_refs=refs,
        )
        if verification.get("status") != "accepted":
            bad.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "reason": "verify_evidence_failed",
                    "invalid_refs": verification.get("invalid_refs", []),
                }
            )
    if isinstance(report, dict):
        if int(report.get("invalid_count") or 0) != 0 or int(report.get("unresolved_count") or 0) != 0:
            bad.append({"reason": "bundle_report_not_clean", "report": report})
    else:
        bad.append({"reason": "missing_bundle_verify_report"})

    ok = bool(claims) and not bad
    return _check(
        "bundle_claim_evidence",
        ok,
        "Bundled IR-input claims use only raw evidence refs and pass structural re-verification.",
        {
            "claim_count": len(claims),
            "evidence_type_counts": evidence_type_counts,
            "bad": bad[:25],
        },
    )


def _check_coverage_terms(bundle_dir: Path, coverage_terms: list[str]) -> dict[str, Any]:
    claims = _read_jsonl(bundle_dir / "claims_bundle.jsonl")
    corpus = "\n".join(str(claim.get("text") or "") for claim in claims).lower()
    missing = [term for term in coverage_terms if term.lower() not in corpus]
    return _check(
        "coverage_terms",
        not missing,
        "Configured acceptance terms appear in verified claim text.",
        {"terms": coverage_terms, "missing": missing},
    )


def run_ir_before_acceptance_audit(
    *,
    doc_id: str,
    processed_doc_root: str | Path,
    bundle_dir: str | Path,
    reading_dirs: list[str | Path],
    discovery_dirs: list[str | Path],
    coverage_terms: list[str] | None = None,
    output_path: str | Path | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run mechanical checks over IR-before artifacts."""
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    processed_root = Path(processed_doc_root)
    bundle = Path(bundle_dir)
    readings = [Path(path) for path in reading_dirs]
    discoveries = [Path(path) for path in discovery_dirs]

    checks = [
        _check_agent_prompt_tool_discipline(root),
        _check_processed_page_assets(processed_root),
        _check_page_tool(doc_id),
        _check_assets(processed_root),
        _check_reports("discovery_reports", discoveries),
        _check_reports("reading_reports", readings),
        _check_bundle_claim_evidence(doc_id, bundle),
        _check_coverage_terms(bundle, coverage_terms or []),
    ]
    failed = [check for check in checks if check["status"] != "passed"]
    report = {
        "status": "accepted" if not failed else "rejected",
        "doc_id": doc_id,
        "processed_doc_root": str(processed_root),
        "bundle_dir": str(bundle),
        "summary": {
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "total": len(checks),
        },
        "checks": checks,
    }
    if output_path is not None:
        _write_json(Path(output_path), report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit IR-before SpecIndex artifacts.")
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--processed-doc-root", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--reading", action="append", required=True)
    parser.add_argument("--discovery", action="append", required=True)
    parser.add_argument("--coverage-term", action="append", default=[])
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = run_ir_before_acceptance_audit(
        doc_id=args.doc_id,
        processed_doc_root=args.processed_doc_root,
        bundle_dir=args.bundle,
        reading_dirs=[Path(path) for path in args.reading],
        discovery_dirs=[Path(path) for path in args.discovery],
        coverage_terms=list(args.coverage_term),
        output_path=args.out,
    )
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
