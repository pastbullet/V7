"""SpecIndex asset and evidence tools.

These tools read already-materialized SpecIndex artifacts.  They deliberately
perform only structural checks: object existence, document ownership, and quote
containment in the referenced raw object.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROCESSED_SPECS_DIR = "processed_specs"
ALLOWED_EVIDENCE_TYPES = {"text_span", "table_cell", "figure_crop", "figure_region"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return _read_json(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _candidate_roots() -> list[Path]:
    roots = [Path.cwd() / PROCESSED_SPECS_DIR]
    project_root = Path(__file__).resolve().parents[2]
    project_processed = project_root / PROCESSED_SPECS_DIR
    if project_processed not in roots:
        roots.append(project_processed)
    return roots


def _resolve_doc_root(doc_id: str) -> Path:
    candidates = [doc_id]
    stem = Path(doc_id).stem
    if stem and stem not in candidates:
        candidates.append(stem)

    for processed_root in _candidate_roots():
        if not processed_root.exists():
            continue
        for candidate_doc_id in candidates:
            for candidate in processed_root.glob(f"*/{candidate_doc_id}"):
                if candidate.is_dir():
                    return candidate
    raise FileNotFoundError(f"SpecIndex document not found: {doc_id}")


def _resolve_asset_doc_root(asset_kind: str, asset_id: str, doc_id: str | None = None) -> Path:
    if doc_id:
        root = _resolve_doc_root(doc_id)
        if (root / asset_kind / asset_id).exists():
            return root
        raise FileNotFoundError(f"Asset not found in {doc_id}: {asset_id}")

    for processed_root in _candidate_roots():
        if not processed_root.exists():
            continue
        for candidate in processed_root.glob(f"*/*/{asset_kind}/{asset_id}"):
            if candidate.is_dir():
                return candidate.parents[1]
    raise FileNotFoundError(f"Asset not found: {asset_id}")


def _parse_page_range(page_range: str | None) -> set[int] | None:
    if page_range is None:
        return None
    text = str(page_range).strip()
    if not text:
        return None
    pages: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if start > end:
                start, end = end, start
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))
    return pages


def _asset_pages(asset: dict[str, Any]) -> set[int]:
    pages = asset.get("pages")
    if isinstance(pages, list):
        result: set[int] = set()
        for page in pages:
            try:
                result.add(int(page))
            except (TypeError, ValueError):
                continue
        return result
    page = asset.get("page")
    try:
        return {int(page)}
    except (TypeError, ValueError):
        return set()


def _load_asset_manifest(doc_root: Path) -> list[dict[str, Any]]:
    return _read_jsonl(doc_root / "assets" / "assets_manifest.jsonl")


def list_assets(
    doc_id: str,
    page_range: str | None = None,
    section_id: str | None = None,
    type: str | None = None,
    caption_query: str | None = None,
) -> dict[str, Any]:
    """List stable table/figure assets for a document."""
    try:
        doc_root = _resolve_doc_root(doc_id)
    except FileNotFoundError as exc:
        return {"error": str(exc), "doc_id": doc_id}

    requested_pages = _parse_page_range(page_range)
    caption_filter = str(caption_query or "").strip().lower()
    assets: list[dict[str, Any]] = []
    for asset in _load_asset_manifest(doc_root):
        if type and asset.get("type") != type:
            continue
        if section_id and asset.get("section_id") != section_id:
            continue
        if requested_pages is not None and not (_asset_pages(asset) & requested_pages):
            continue
        if caption_filter and caption_filter not in str(asset.get("caption") or "").lower():
            continue
        assets.append(asset)

    return {
        "doc_id": doc_id,
        "asset_count": len(assets),
        "assets": assets,
        "source_manifest": str(doc_root / "assets" / "assets_manifest.jsonl"),
    }


def get_table(table_id: str, doc_id: str | None = None, view: str = "full") -> dict[str, Any]:
    """Return a logical table asset, including cells and raw crop path."""
    try:
        doc_root = _resolve_asset_doc_root("tables", table_id, doc_id)
    except FileNotFoundError as exc:
        return {"error": str(exc), "table_id": table_id}

    table_root = doc_root / "tables" / table_id
    meta = _read_json_if_exists(table_root / "table_meta.json") or {}
    cells = _read_jsonl(table_root / "cells.jsonl")
    crop_path = table_root / str(meta.get("source_crop", "crop.png"))

    table: dict[str, Any] = {
        "table_id": table_id,
        "doc_id": doc_root.name,
        "view": view,
        "meta": meta,
        "markdown": _read_text_if_exists(table_root / "table.md"),
        "table_json": _read_json_if_exists(table_root / "table.json"),
        "cells": cells,
        "cell_count": len(cells),
        "context": _read_text_if_exists(table_root / str(meta.get("context_file", "context.md"))),
        "crop_path": str(crop_path),
    }
    return {"table": table}


def get_image(image_id: str, doc_id: str | None = None, view: str = "full") -> dict[str, Any]:
    """Return a figure/image asset, including crop path and derived summary."""
    try:
        doc_root = _resolve_asset_doc_root("figures", image_id, doc_id)
    except FileNotFoundError as exc:
        return {"error": str(exc), "image_id": image_id}

    image_root = doc_root / "figures" / image_id
    meta = _read_json_if_exists(image_root / "figure_meta.json") or {}
    crop_path = image_root / str(meta.get("source_crop", "crop.png"))
    summary_file = str(meta.get("vision_summary_file", "vision_summary.json"))

    image: dict[str, Any] = {
        "image_id": image_id,
        "doc_id": doc_root.name,
        "view": view,
        "meta": meta,
        "context": _read_text_if_exists(image_root / str(meta.get("context_file", "context.md"))),
        "vision_summary": _read_json_if_exists(image_root / summary_file),
        "crop_path": str(crop_path),
    }
    return {"image": image}


def _find_text_span(doc_root: Path, span_id: str) -> dict[str, Any] | None:
    for text_path in sorted((doc_root / "pages").glob("page_*/text.json")):
        payload = _read_json_if_exists(text_path)
        if not isinstance(payload, dict):
            continue
        for span in payload.get("spans", []):
            if isinstance(span, dict) and span.get("span_id") == span_id:
                return {
                    **span,
                    "doc_id": doc_root.name,
                    "page": span.get("page", payload.get("page")),
                    "source_path": str(text_path),
                }
    return None


def _find_table_cell(doc_root: Path, asset_id: str, cell_id: str) -> dict[str, Any] | None:
    table_root = doc_root / "tables" / asset_id
    if not table_root.exists():
        return None
    for cell in _read_jsonl(table_root / "cells.jsonl"):
        if cell.get("cell_id") == cell_id:
            return {
                **cell,
                "doc_id": doc_root.name,
                "asset_id": asset_id,
                "source_path": str(table_root / "cells.jsonl"),
            }
    return None


def _find_figure_crop(doc_root: Path, asset_id: str) -> dict[str, Any] | None:
    image_root = doc_root / "figures" / asset_id
    meta = _read_json_if_exists(image_root / "figure_meta.json")
    if not isinstance(meta, dict):
        return None
    crop_path = image_root / str(meta.get("source_crop", "crop.png"))
    if not crop_path.exists():
        return None
    return {
        "doc_id": doc_root.name,
        "asset_id": asset_id,
        "meta": meta,
        "crop_path": str(crop_path),
    }


def _quote_is_contained(obj: dict[str, Any], quote: Any) -> bool:
    if quote is None:
        return True
    quote_text = str(quote)
    if not quote_text:
        return True
    text = obj.get("text")
    return isinstance(text, str) and quote_text in text


def _invalid_ref(ref: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"ref": ref, "reason": reason}


def _normalize_evidence_ref(ref: dict[str, Any]) -> dict[str, Any]:
    """Normalize structurally wrapped evidence refs into the canonical flat shape."""
    if "type" in ref:
        return dict(ref)

    wrapper_keys = [key for key in ALLOWED_EVIDENCE_TYPES if key in ref]
    if len(wrapper_keys) != 1:
        return dict(ref)

    wrapper_type = wrapper_keys[0]
    wrapped = ref.get(wrapper_type)
    if not isinstance(wrapped, dict):
        return dict(ref)

    wrapped_type = wrapped.get("type")
    if wrapped_type is not None and wrapped_type != wrapper_type:
        return dict(ref)

    normalized = dict(wrapped)
    normalized["type"] = wrapper_type
    return normalized


def verify_evidence(
    doc_id: str,
    claim: str,
    evidence_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Structurally verify that claim evidence points to raw SpecIndex objects."""
    try:
        doc_root = _resolve_doc_root(doc_id)
    except FileNotFoundError as exc:
        return {
            "doc_id": doc_id,
            "claim": claim,
            "status": "invalid",
            "checked_refs": [],
            "invalid_refs": [{"ref": {}, "reason": str(exc)}],
            "invalid_count": 1,
        }

    checked_refs: list[dict[str, Any]] = []
    invalid_refs: list[dict[str, Any]] = []

    if not evidence_refs:
        invalid_refs.append(_invalid_ref({}, "accepted claims require at least one raw evidence ref"))

    for ref in evidence_refs or []:
        if not isinstance(ref, dict):
            invalid_refs.append(_invalid_ref({"value": ref}, "evidence ref must be an object"))
            continue

        ref = _normalize_evidence_ref(ref)
        ref_type = ref.get("type")
        if ref_type not in ALLOWED_EVIDENCE_TYPES:
            invalid_refs.append(
                _invalid_ref(ref, f"{ref_type} is not an allowed raw evidence type")
            )
            continue

        if ref_type == "text_span":
            span_id = ref.get("span_id")
            if not span_id:
                invalid_refs.append(_invalid_ref(ref, "text_span requires span_id"))
                continue
            found = _find_text_span(doc_root, str(span_id))
            if found is None:
                invalid_refs.append(_invalid_ref(ref, f"text span not found: {span_id}"))
                continue
            if not _quote_is_contained(found, ref.get("quote")):
                invalid_refs.append(_invalid_ref(ref, "quote not found in text span"))
                continue
            checked_refs.append({"type": ref_type, "ref": ref, "object": found})
            continue

        if ref_type == "table_cell":
            asset_id = ref.get("asset_id")
            cell_id = ref.get("cell_id")
            if not asset_id or not cell_id:
                invalid_refs.append(_invalid_ref(ref, "table_cell requires asset_id and cell_id"))
                continue
            found = _find_table_cell(doc_root, str(asset_id), str(cell_id))
            if found is None:
                invalid_refs.append(_invalid_ref(ref, f"table cell not found: {asset_id}/{cell_id}"))
                continue
            if not _quote_is_contained(found, ref.get("quote")):
                invalid_refs.append(_invalid_ref(ref, "quote not found in table cell"))
                continue
            checked_refs.append({"type": ref_type, "ref": ref, "object": found})
            continue

        asset_id = ref.get("asset_id")
        if not asset_id:
            invalid_refs.append(_invalid_ref(ref, f"{ref_type} requires asset_id"))
            continue
        found = _find_figure_crop(doc_root, str(asset_id))
        if found is None:
            invalid_refs.append(_invalid_ref(ref, f"figure crop not found: {asset_id}"))
            continue
        checked_refs.append({"type": ref_type, "ref": ref, "object": found})

    status = "accepted" if not invalid_refs else "invalid"
    return {
        "doc_id": doc_id,
        "claim": claim,
        "status": status,
        "checked_refs": checked_refs,
        "invalid_refs": invalid_refs,
        "invalid_count": len(invalid_refs),
    }
