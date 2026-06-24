"""Document ingestion orchestration for end-to-end Agentic RAG pipeline."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.tools.registry import get_doc_config, is_document_processed, register_document
from src.tools.pathing import chunk_dir_for_doc, content_root_for_doc, page_index_path_for_doc

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class ProcessResult:
    """Result of a document processing run."""

    doc_name: str
    doc_stem: str
    pdf_path: str
    page_index_json: str
    chunks_dir: str
    content_dir: str
    total_pages: int
    index_built: bool = False
    structure_built: bool = False
    content_built: bool = False
    summary_built: bool = False
    registered: bool = False


def _safe_doc_stem(stem: str) -> str:
    clean = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in stem.strip())
    return clean or "document"


def _canonical_doc_name(name_or_path: str) -> str:
    name = Path(name_or_path).name.strip()
    if not name:
        raise ValueError("Document name is empty")
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name


def _to_registry_path(path: Path, base: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(base.resolve()))
    except ValueError:
        return str(path)


def _read_total_pages_from_content_dir(content_dir: Path) -> int:
    max_page = 0
    for fp in sorted(content_dir.glob("content_*.json")):
        try:
            payload = json.loads(fp.read_text(encoding="utf-8"))
            end_page = payload.get("end_page")
            if isinstance(end_page, int):
                max_page = max(max_page, end_page)
        except (json.JSONDecodeError, OSError):
            pass

        # fallback to filename pattern content_{start}_{end}.json
        parts = fp.stem.split("_")
        if len(parts) >= 3:
            try:
                max_page = max(max_page, int(parts[2]))
            except ValueError:
                pass

    if max_page <= 0:
        raise RuntimeError(f"Failed to infer total_pages from content dir: {content_dir}")
    return max_page


def _specindex_doc_root(project_root: Path, doc_stem: str) -> Path:
    return project_root / "processed_specs" / "local" / doc_stem


def _rounded_bbox(raw_bbox: Any) -> list[float]:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return [0.0, 0.0, 0.0, 0.0]
    result: list[float] = []
    for value in raw_bbox:
        try:
            result.append(round(float(value), 2))
        except (TypeError, ValueError):
            result.append(0.0)
    return result


def _legacy_content_pages(content_dir: Path) -> dict[int, dict[str, Any]]:
    pages: dict[int, dict[str, Any]] = {}
    for fp in sorted(content_dir.glob("content_*.json")):
        try:
            payload = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for item in payload.get("pages", []):
            if not isinstance(item, dict):
                continue
            page_num = item.get("page_num")
            if isinstance(page_num, int):
                pages[page_num] = item
    return pages


def _fallback_specindex_pages_from_content(
    *,
    doc_root: Path,
    doc_stem: str,
    source_pdf: Path,
    content_dir: Path,
) -> int:
    pages = _legacy_content_pages(content_dir)
    for page_num, item in pages.items():
        page_dir = doc_root / "pages" / f"page_{page_num:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        text = str(item.get("layout_text") or item.get("text") or "")
        payload = {
            "doc_id": doc_stem,
            "source_pdf": str(source_pdf),
            "page": page_num,
            "spans": [
                {
                    "span_id": f"p{page_num:03d}_s0001",
                    "text": text,
                    "bbox": [0.0, 0.0, 0.0, 0.0],
                    "bbox_status": "unavailable",
                }
            ] if text else [],
            "asset_ids": [],
        }
        (page_dir / "text.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return len(pages)


def _extract_fitz_text_spans(page: Any, page_num: int) -> list[dict[str, Any]]:
    text_dict = page.get_text("dict") or {}
    spans: list[dict[str, Any]] = []
    span_index = 1
    for block_index, block in enumerate(text_dict.get("blocks", []), start=1):
        if not isinstance(block, dict):
            continue
        for line_index, line in enumerate(block.get("lines", []), start=1):
            if not isinstance(line, dict):
                continue
            for raw_span_index, span in enumerate(line.get("spans", []), start=1):
                if not isinstance(span, dict):
                    continue
                text = str(span.get("text") or "")
                if not text.strip():
                    continue
                spans.append(
                    {
                        "span_id": f"p{page_num:03d}_s{span_index:04d}",
                        "text": text,
                        "bbox": _rounded_bbox(span.get("bbox")),
                        "block_index": block_index,
                        "line_index": line_index,
                        "span_index": raw_span_index,
                    }
                )
                span_index += 1
    return spans


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bbox_from_tuple(raw_bbox: Any) -> list[float]:
    return _rounded_bbox(list(raw_bbox) if isinstance(raw_bbox, tuple) else raw_bbox)


def _render_crop(page: Any, bbox: list[float], out_path: Path) -> None:
    import fitz

    rect = fitz.Rect(*bbox)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect, alpha=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_path))


def _line_bbox(raw_bbox: Any) -> list[float]:
    return _bbox_from_tuple(raw_bbox)


def _clean_caption_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_nearby_caption(
    page: Any,
    bbox: list[float],
    *,
    label: str,
    fallback: str,
) -> str:
    """Find the nearest preceding Table/Figure caption for an asset crop."""
    pattern = re.compile(rf"^\s*{re.escape(label)}\s+\d+\b", re.IGNORECASE)
    asset_top = float(bbox[1]) if len(bbox) >= 2 else 0.0
    candidates: list[tuple[float, str]] = []
    text_dict = page.get_text("dict") or {}

    for block in text_dict.get("blocks", []):
        if not isinstance(block, dict) or block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            if not isinstance(line, dict):
                continue
            parts: list[str] = []
            for span in line.get("spans", []):
                if isinstance(span, dict) and isinstance(span.get("text"), str):
                    parts.append(span["text"])
            text = _clean_caption_text(" ".join(parts))
            if not text or not pattern.match(text):
                continue
            line_bbox = _line_bbox(line.get("bbox"))
            line_bottom = line_bbox[3]
            distance = asset_top - line_bottom
            if -3 <= distance <= 90:
                candidates.append((abs(distance), text))

    if not candidates:
        return fallback
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _table_to_markdown(rows: list[list[Any]]) -> str:
    if not rows:
        return ""
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return ""
    normalized: list[list[str]] = []
    for row in rows:
        cells = ["" if cell is None else str(cell).replace("\n", "<br>").strip() for cell in row]
        cells.extend([""] * (width - len(cells)))
        normalized.append(cells)
    header = normalized[0]
    lines = [
        f"| {' | '.join(header)} |",
        f"| {' | '.join(['---'] * width)} |",
    ]
    for row in normalized[1:]:
        lines.append(f"| {' | '.join(row)} |")
    return "\n".join(lines)


def _materialize_table_asset(
    *,
    doc_root: Path,
    fitz_page: Any,
    table: Any,
    extracted_rows: list[list[Any]],
    page_num: int,
    asset_id: str,
) -> dict[str, Any]:
    table_root = doc_root / "tables" / asset_id
    bbox = _bbox_from_tuple(table.bbox)
    crop_name = "crop.png"
    _render_crop(fitz_page, bbox, table_root / crop_name)
    caption = _extract_nearby_caption(
        fitz_page,
        bbox,
        label="Table",
        fallback=f"Table fragment on page {page_num}",
    )

    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.rows, start=1):
        row_cells = getattr(row, "cells", []) or []
        row_values = extracted_rows[row_index - 1] if row_index - 1 < len(extracted_rows) else []
        for col_index, raw_cell_bbox in enumerate(row_cells, start=1):
            text = ""
            if col_index - 1 < len(row_values):
                value = row_values[col_index - 1]
                text = "" if value is None else str(value).strip()
            cell = {
                "cell_id": f"r{row_index}c{col_index}",
                "row": row_index,
                "col": col_index,
                "text": text,
                "page": page_num,
                "bbox": _bbox_from_tuple(raw_cell_bbox),
            }
            cells.append(cell)

    _write_text(table_root / "cells.jsonl", "\n".join(json.dumps(cell, ensure_ascii=False) for cell in cells) + ("\n" if cells else ""))
    _write_text(table_root / "table.md", _table_to_markdown(extracted_rows))
    _write_json(table_root / "table.json", {"rows": extracted_rows})
    _write_text(table_root / "context.md", "")

    meta = {
        "asset_id": asset_id,
        "type": "table",
        "caption": caption,
        "pages": [page_num],
        "bbox": bbox,
        "source_crop": crop_name,
        "context_file": "context.md",
        "source_pdf_page": page_num,
    }
    _write_json(table_root / "table_meta.json", meta)
    return {
        "asset_id": asset_id,
        "type": "table",
        "caption": caption,
        "pages": [page_num],
        "bbox": bbox,
        "path": f"tables/{asset_id}/table_meta.json",
    }


def _materialize_figure_asset(
    *,
    doc_root: Path,
    fitz_page: Any,
    image_block: dict[str, Any],
    page_num: int,
    asset_id: str,
) -> dict[str, Any]:
    figure_root = doc_root / "figures" / asset_id
    bbox = _bbox_from_tuple(image_block.get("bbox"))
    crop_name = "crop.png"
    _render_crop(fitz_page, bbox, figure_root / crop_name)
    caption = _extract_nearby_caption(
        fitz_page,
        bbox,
        label="Figure",
        fallback=f"Figure crop on page {page_num}",
    )
    _write_text(figure_root / "context.md", "")
    _write_json(
        figure_root / "vision_summary.json",
        {
            "derived": True,
            "summary": "",
            "note": "Derived summaries are not raw evidence; cite crop or regions instead.",
        },
    )
    meta = {
        "asset_id": asset_id,
        "type": "figure",
        "caption": caption,
        "pages": [page_num],
        "bbox": bbox,
        "source_crop": crop_name,
        "context_file": "context.md",
        "vision_summary_file": "vision_summary.json",
        "source_pdf_page": page_num,
    }
    _write_json(figure_root / "figure_meta.json", meta)
    return {
        "asset_id": asset_id,
        "type": "figure",
        "caption": caption,
        "pages": [page_num],
        "bbox": bbox,
        "path": f"figures/{asset_id}/figure_meta.json",
    }


def _normalize_table_header(rows: Any) -> tuple[str, ...]:
    if not isinstance(rows, list) or not rows:
        return ()
    header = rows[0]
    if not isinstance(header, list):
        return ()
    return tuple(str(cell or "").strip().lower() for cell in header)


def _load_table_fragment(doc_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(manifest["asset_id"])
    table_root = doc_root / "tables" / asset_id
    meta = json.loads((table_root / "table_meta.json").read_text(encoding="utf-8"))
    table_json = json.loads((table_root / "table.json").read_text(encoding="utf-8"))
    cells = [
        json.loads(line)
        for line in (table_root / "cells.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = table_json.get("rows", [])
    return {
        "asset_id": asset_id,
        "root": table_root,
        "manifest": manifest,
        "meta": meta,
        "rows": rows if isinstance(rows, list) else [],
        "cells": cells,
        "header": _normalize_table_header(rows),
        "pages": meta.get("pages", manifest.get("pages", [])),
    }


def _can_stitch_table_fragment(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    if not previous.get("header") or previous.get("header") != current.get("header"):
        return False
    previous_pages = previous.get("pages") or []
    current_pages = current.get("pages") or []
    if not previous_pages or not current_pages:
        return False
    try:
        return int(current_pages[0]) == int(previous_pages[-1]) + 1
    except (TypeError, ValueError):
        return False


def _group_table_fragments(fragments: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for fragment in fragments:
        if groups and _can_stitch_table_fragment(groups[-1][-1], fragment):
            groups[-1].append(fragment)
        else:
            groups.append([fragment])
    return groups


def _rewrite_page_asset_ids(doc_root: Path, replacements: dict[str, str]) -> None:
    if not replacements:
        return
    for text_path in sorted((doc_root / "pages").glob("page_*/text.json")):
        payload = json.loads(text_path.read_text(encoding="utf-8"))
        asset_ids = payload.get("asset_ids", [])
        if not isinstance(asset_ids, list):
            continue
        rewritten: list[str] = []
        changed = False
        for asset_id in asset_ids:
            new_id = replacements.get(str(asset_id), str(asset_id))
            if new_id != asset_id:
                changed = True
            if new_id not in rewritten:
                rewritten.append(new_id)
        if changed:
            payload["asset_ids"] = rewritten
            text_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_logical_table_group(doc_root: Path, group: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    primary = group[0]
    asset_id = primary["asset_id"]
    replacements: dict[str, str] = {}
    if len(group) == 1:
        meta = dict(primary["meta"])
        meta["logical_table"] = False
        _write_json(primary["root"] / "table_meta.json", meta)
        manifest = dict(primary["manifest"])
        manifest["logical_table"] = False
        manifest["fragment_ids"] = [asset_id]
        return manifest, replacements

    logical_rows: list[list[Any]] = []
    logical_cells: list[dict[str, Any]] = []
    logical_row_index = 1
    pages: list[int] = []
    fragment_ids = [str(fragment["asset_id"]) for fragment in group]

    for fragment_index, fragment in enumerate(group):
        for page in fragment.get("pages", []):
            try:
                page_int = int(page)
            except (TypeError, ValueError):
                continue
            if page_int not in pages:
                pages.append(page_int)

        rows = fragment["rows"]
        cells_by_row: dict[int, list[dict[str, Any]]] = {}
        for cell in fragment["cells"]:
            try:
                row_num = int(cell.get("row"))
            except (TypeError, ValueError):
                continue
            cells_by_row.setdefault(row_num, []).append(cell)

        start_row = 1 if fragment_index == 0 else 2
        for row_num, row_values in enumerate(rows, start=1):
            if row_num < start_row:
                continue
            logical_rows.append(row_values)
            for source_cell in sorted(cells_by_row.get(row_num, []), key=lambda item: int(item.get("col", 0))):
                col = int(source_cell.get("col", 0))
                cell = {
                    **source_cell,
                    "cell_id": f"r{logical_row_index}c{col}",
                    "row": logical_row_index,
                    "source_fragment_id": fragment["asset_id"],
                    "source_cell_id": source_cell.get("cell_id"),
                }
                logical_cells.append(cell)
            logical_row_index += 1

    table_root = primary["root"]
    _write_text(
        table_root / "cells.jsonl",
        "\n".join(json.dumps(cell, ensure_ascii=False) for cell in logical_cells)
        + ("\n" if logical_cells else ""),
    )
    _write_text(table_root / "table.md", _table_to_markdown(logical_rows))
    _write_json(table_root / "table.json", {"rows": logical_rows})

    bbox = primary["meta"].get("bbox", primary["manifest"].get("bbox"))
    meta = {
        **primary["meta"],
        "asset_id": asset_id,
        "type": "table",
        "caption": primary["meta"].get("caption", f"Logical table starting page {pages[0] if pages else ''}"),
        "pages": pages,
        "bbox": bbox,
        "logical_table": True,
        "fragment_ids": fragment_ids,
        "continuation": {
            "type": "adjacent_same_header",
            "header_source_fragment": asset_id,
        },
        "fragment_crops": [
            {
                "fragment_id": fragment["asset_id"],
                "pages": fragment.get("pages", []),
                "crop_path": f"tables/{fragment['asset_id']}/{fragment['meta'].get('source_crop', 'crop.png')}",
            }
            for fragment in group
        ],
    }
    _write_json(table_root / "table_meta.json", meta)

    for fragment in group[1:]:
        replacements[str(fragment["asset_id"])] = asset_id

    manifest = {
        **primary["manifest"],
        "asset_id": asset_id,
        "type": "table",
        "caption": meta["caption"],
        "pages": pages,
        "bbox": bbox,
        "path": f"tables/{asset_id}/table_meta.json",
        "logical_table": True,
        "fragment_ids": fragment_ids,
    }
    return manifest, replacements


def _stitch_logical_tables(doc_root: Path, manifest_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_entries = [entry for entry in manifest_entries if entry.get("type") == "table"]
    other_entries = [entry for entry in manifest_entries if entry.get("type") != "table"]
    if not table_entries:
        return manifest_entries

    fragments = [_load_table_fragment(doc_root, entry) for entry in table_entries]
    fragments.sort(key=lambda item: (item.get("pages") or [0])[0])
    stitched_entries: list[dict[str, Any]] = []
    replacements: dict[str, str] = {}
    for group in _group_table_fragments(fragments):
        manifest, group_replacements = _write_logical_table_group(doc_root, group)
        stitched_entries.append(manifest)
        replacements.update(group_replacements)

    _rewrite_page_asset_ids(doc_root, replacements)
    return stitched_entries + other_entries


def _materialize_specindex_page_assets(
    *,
    project_root: Path,
    source_pdf: Path,
    doc_stem: str,
    content_dir: Path,
    progress_callback: ProgressCallback | None,
) -> Path:
    """Write the first SpecIndex raw evidence layout for page images and spans."""
    doc_root = _specindex_doc_root(project_root, doc_stem)
    pages_root = doc_root / "pages"
    assets_root = doc_root / "assets"
    pages_root.mkdir(parents=True, exist_ok=True)
    assets_root.mkdir(parents=True, exist_ok=True)

    page_count = 0
    manifest_entries: list[dict[str, Any]] = []
    table_count = 0
    figure_count = 0
    try:
        import fitz
        import pdfplumber

        with fitz.open(source_pdf) as doc, pdfplumber.open(source_pdf) as pdf:
            for page_idx in range(doc.page_count):
                page_num = page_idx + 1
                page = doc.load_page(page_idx)
                page_assets: list[str] = []
                page_dir = pages_root / f"page_{page_num:03d}"
                page_dir.mkdir(parents=True, exist_ok=True)

                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                pix.save(str(page_dir / "page.png"))

                if page_idx < len(pdf.pages):
                    pdf_page = pdf.pages[page_idx]
                    for table in pdf_page.find_tables():
                        extracted_rows = table.extract() or []
                        if not extracted_rows:
                            continue
                        table_count += 1
                        asset_id = f"table_{table_count:04d}"
                        manifest = _materialize_table_asset(
                            doc_root=doc_root,
                            fitz_page=page,
                            table=table,
                            extracted_rows=extracted_rows,
                            page_num=page_num,
                            asset_id=asset_id,
                        )
                        manifest_entries.append(manifest)
                        page_assets.append(asset_id)

                text_dict = page.get_text("dict") or {}
                for block in text_dict.get("blocks", []):
                    if not isinstance(block, dict) or block.get("type") != 1:
                        continue
                    figure_count += 1
                    asset_id = f"figure_{figure_count:04d}"
                    manifest = _materialize_figure_asset(
                        doc_root=doc_root,
                        fitz_page=page,
                        image_block=block,
                        page_num=page_num,
                        asset_id=asset_id,
                    )
                    manifest_entries.append(manifest)
                    page_assets.append(asset_id)

                payload = {
                    "doc_id": doc_stem,
                    "source_pdf": str(source_pdf),
                    "page": page_num,
                    "spans": _extract_fitz_text_spans(page, page_num),
                    "asset_ids": page_assets,
                }
                (page_dir / "text.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                page_count += 1
    except Exception as exc:
        logger.warning("[ingest] SpecIndex PDF page materialization fell back to content DB: %s", exc)
        page_count = _fallback_specindex_pages_from_content(
            doc_root=doc_root,
            doc_stem=doc_stem,
            source_pdf=source_pdf,
            content_dir=content_dir,
        )

    manifest_entries = _stitch_logical_tables(doc_root, manifest_entries)
    (assets_root / "assets_manifest.jsonl").write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False) for entry in manifest_entries)
        + ("\n" if manifest_entries else ""),
        encoding="utf-8",
    )
    _emit_progress(
        progress_callback,
        {
            "type": "stage_done",
            "stage": "specindex_pages",
            "doc_name": source_pdf.name,
            "doc_root": str(doc_root),
            "page_count": page_count,
            "asset_count": len(manifest_entries),
        },
    )
    return doc_root


def _structure_ready(chunks_dir: Path) -> bool:
    manifest = chunks_dir / "manifest.json"
    if not manifest.exists():
        return False
    return any(chunks_dir.glob("part_*.json"))


def _content_ready(content_dir: Path) -> bool:
    if not content_dir.is_dir():
        return False
    return any(content_dir.glob("content_*.json"))


def _load_page_index_builder() -> Callable[..., dict[str, Any]]:
    from page_index import page_index

    return page_index


def _load_structure_helpers():
    from structure_chunker import (
        chunk_document_structure,
        load_root_from_page_index_json,
        save_parts_to_folder,
    )

    return load_root_from_page_index_json, chunk_document_structure, save_parts_to_folder


def _build_structure_chunks(
    *,
    page_index_json: Path,
    chunks_dir: Path,
    structure_max_limit: int,
) -> None:
    (
        load_root_from_page_index_json,
        chunk_document_structure,
        save_parts_to_folder,
    ) = _load_structure_helpers()

    root, chunk_doc_name = load_root_from_page_index_json(str(page_index_json))
    parts = chunk_document_structure(
        root_node=root,
        doc_name=chunk_doc_name,
        max_limit=structure_max_limit,
    )
    save_parts_to_folder(parts, chunks_dir)


def _load_content_builder() -> Callable[..., list[Path]]:
    from build_content_db import build_content_db

    return build_content_db


def _emit_progress(progress_callback: ProgressCallback | None, payload: dict[str, Any]) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(payload)
    except Exception:
        logger.exception("progress_callback failed in ingest pipeline")


def _flag_enabled(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
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


def _node_page_set(node: dict[str, Any]) -> set[int]:
    start = node.get("start_index")
    end = node.get("end_index")
    if not isinstance(start, int) or not isinstance(end, int) or start <= 0:
        return set()
    if end < start:
        start, end = end, start
    return set(range(start, end + 1))


def _asset_page_set(asset: dict[str, Any]) -> set[int]:
    pages = asset.get("pages")
    if isinstance(pages, list):
        result: set[int] = set()
        for page in pages:
            try:
                result.add(int(page))
            except (TypeError, ValueError):
                continue
        return result
    try:
        return {int(asset.get("page"))}
    except (TypeError, ValueError):
        return set()


def _compact_text(value: Any, *, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_table_preview(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return ""
    preview_rows: list[str] = []
    for row in rows[:2]:
        if not isinstance(row, list):
            continue
        cells = [_compact_text(cell, limit=60) for cell in row[:6]]
        cells = [cell for cell in cells if cell]
        if cells:
            preview_rows.append(" | ".join(cells))
    return _compact_text(" / ".join(preview_rows), limit=240)


def _summary_table_asset(doc_root: Path, asset: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(asset.get("asset_id") or "")
    table_root = doc_root / "tables" / asset_id
    table_json = _read_json_if_exists(table_root / "table.json") or {}
    rows = table_json.get("rows") if isinstance(table_json, dict) else []
    cells = _read_jsonl_if_exists(table_root / "cells.jsonl")
    row_count = len(rows) if isinstance(rows, list) else None
    result: dict[str, Any] = {
        "asset_id": asset_id,
        "caption": _compact_text(asset.get("caption"), limit=180),
        "pages": sorted(_asset_page_set(asset)),
        "cell_count": len(cells),
    }
    if row_count is not None:
        result["row_count"] = row_count
    preview = _format_table_preview(rows)
    if preview:
        result["preview"] = preview
    return result


def _summary_figure_asset(doc_root: Path, asset: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(asset.get("asset_id") or "")
    figure_root = doc_root / "figures" / asset_id
    vision = _read_json_if_exists(figure_root / "vision_summary.json")
    result: dict[str, Any] = {
        "asset_id": asset_id,
        "caption": _compact_text(asset.get("caption"), limit=180),
        "pages": sorted(_asset_page_set(asset)),
    }
    if isinstance(vision, dict):
        summary = _compact_text(vision.get("summary"), limit=220)
        if summary:
            result["summary"] = summary
    return result


def _load_summary_assets_for_node(
    *,
    doc_root: Path | None,
    manifest_entries: list[dict[str, Any]],
    node: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if doc_root is None:
        return {"tables": [], "figures": []}
    node_pages = _node_page_set(node)
    if not node_pages:
        return {"tables": [], "figures": []}

    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    for asset in manifest_entries:
        if not (_asset_page_set(asset) & node_pages):
            continue
        if asset.get("type") == "table":
            tables.append(_summary_table_asset(doc_root, asset))
        elif asset.get("type") == "figure":
            figures.append(_summary_figure_asset(doc_root, asset))
    return {"tables": tables, "figures": figures}


def _materialize_document_summaries(
    *,
    page_index_json: Path,
    content_dir: Path,
    doc_root: Path | None = None,
    model: str | None,
    include_doc_description: bool = False,
) -> dict[str, Any]:
    """Generate node summaries from content_db spans and write them to page_index.json."""
    if not page_index_json.exists():
        raise RuntimeError(f"Page index is missing: {page_index_json}")
    if not content_dir.is_dir():
        raise RuntimeError(f"Content DB is missing: {content_dir}")

    import asyncio

    from src.extract.content_loader import get_node_text
    from utils import (
        create_clean_structure_for_description,
        generate_doc_description,
        generate_summaries_for_nodes,
        structure_to_list,
    )

    page_index_payload = json.loads(page_index_json.read_text(encoding="utf-8"))
    structure = page_index_payload.get("structure", [])
    nodes = [node for node in structure_to_list(structure) if isinstance(node, dict)]
    targets = [node for node in nodes if not str(node.get("summary") or "").strip()]
    ready_nodes: list[dict[str, Any]] = []
    temporary_text_nodes: list[dict[str, Any]] = []
    temporary_asset_nodes: list[tuple[dict[str, Any], bool, Any]] = []
    manifest_entries = (
        _read_jsonl_if_exists(doc_root / "assets" / "assets_manifest.jsonl")
        if doc_root is not None
        else []
    )

    for node in targets:
        direct_text = node.get("text")
        if not (isinstance(direct_text, str) and direct_text.strip()):
            text = get_node_text(node, str(content_dir))
            if not text:
                logger.warning("Skipping summary for node without text: %s", node.get("node_id"))
                continue
            node["text"] = text
            temporary_text_nodes.append(node)
        ready_nodes.append(node)
        had_assets = "_summary_assets" in node
        old_assets = node.get("_summary_assets")
        node["_summary_assets"] = _load_summary_assets_for_node(
            doc_root=doc_root,
            manifest_entries=manifest_entries,
            node=node,
        )
        temporary_asset_nodes.append((node, had_assets, old_assets))

    if ready_nodes:
        try:
            asyncio.run(generate_summaries_for_nodes(ready_nodes, model=model))
        finally:
            for node in temporary_text_nodes:
                node.pop("text", None)
            for node, had_assets, old_assets in temporary_asset_nodes:
                if had_assets:
                    node["_summary_assets"] = old_assets
                else:
                    node.pop("_summary_assets", None)

    if include_doc_description:
        clean_structure = create_clean_structure_for_description(structure)
        page_index_payload["doc_description"] = generate_doc_description(
            clean_structure,
            model=model,
        )

    page_index_json.write_text(
        json.dumps(page_index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "summary_count": len(ready_nodes),
        "summary_missing_count": len(targets) - len(ready_nodes),
        "doc_description_built": include_doc_description,
    }


def _preclassify_document_nodes(
    *,
    doc_stem: str,
    page_index_json: Path,
    content_dir: Path,
    model: str | None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """Populate the classifier cache from original node text after content_db exists."""
    if not page_index_json.exists():
        raise RuntimeError(f"Page index is missing: {page_index_json}")
    if not content_dir.is_dir():
        raise RuntimeError(f"Content DB is missing: {content_dir}")

    import asyncio
    import os

    from src.agent.llm_adapter import LLMAdapter
    from src.extract.classifier import load_or_classify_async
    from src.extract.pipeline import _collect_leaf_nodes

    page_index_payload = json.loads(page_index_json.read_text(encoding="utf-8"))
    nodes = _collect_leaf_nodes(page_index_payload)

    resolved_model = (
        model
        or os.environ.get("PROTOCOL_TWIN_MODEL")
        or os.environ.get("OPENAI_MODEL_NAME")
        or "gpt-4o-mini"
    )
    provider = os.environ.get("PROTOCOL_TWIN_LLM_PROVIDER", "openai")
    resolved_concurrency = max(
        1,
        int(
            concurrency
            if concurrency is not None
            else os.environ.get("PROTOCOL_TWIN_CLASSIFY_CONCURRENCY", "1")
        ),
    )
    llm = LLMAdapter(provider=provider, model=resolved_model)

    labels = asyncio.run(
        load_or_classify_async(
            doc_stem=doc_stem,
            nodes=nodes,
            content_dir=str(content_dir),
            llm=llm,
            concurrency=resolved_concurrency,
        )
    )
    return {
        "node_count": len(nodes),
        "label_count": len(labels),
        "state_machine_count": sum(
            1 for label in labels.values() if getattr(label, "label", None) == "state_machine"
        ),
    }


def _run_preclassification_stage(
    *,
    doc_name: str,
    doc_stem: str,
    page_index_json: Path,
    content_dir: Path,
    model: str | None,
    classify_concurrency: int | None,
    progress_callback: ProgressCallback | None,
) -> None:
    """Best-effort preclassification; downstream CLASSIFY remains the retry point."""
    _emit_progress(
        progress_callback,
        {"type": "stage_start", "stage": "classify", "doc_name": doc_name},
    )
    try:
        classify_summary = _preclassify_document_nodes(
            doc_stem=doc_stem,
            page_index_json=page_index_json,
            content_dir=content_dir,
            model=model,
            concurrency=classify_concurrency,
        )
        _emit_progress(
            progress_callback,
            {
                "type": "stage_done",
                "stage": "classify",
                "doc_name": doc_name,
                **classify_summary,
            },
        )
    except Exception as exc:
        logger.warning(
            "[ingest] Preclassification failed; downstream CLASSIFY can retry: %s",
            exc,
        )
        _emit_progress(
            progress_callback,
            {
                "type": "stage_done",
                "stage": "classify",
                "doc_name": doc_name,
                "error": str(exc),
            },
        )


def _run_summary_materialization_stage(
    *,
    doc_name: str,
    page_index_json: Path,
    content_dir: Path,
    doc_root: Path | None = None,
    model: str | None,
    include_doc_description: bool,
    progress_callback: ProgressCallback | None,
) -> bool:
    _emit_progress(
        progress_callback,
        {"type": "stage_start", "stage": "summary", "doc_name": doc_name},
    )
    summary = _materialize_document_summaries(
        page_index_json=page_index_json,
        content_dir=content_dir,
        doc_root=doc_root,
        model=model,
        include_doc_description=include_doc_description,
    )
    _emit_progress(
        progress_callback,
        {
            "type": "stage_done",
            "stage": "summary",
            "doc_name": doc_name,
            **summary,
        },
    )
    return bool(summary["summary_count"] or summary["doc_description_built"])


def resolve_pdf_for_doc(doc_name_or_path: str) -> Path:
    """Resolve a document to a concrete PDF path.

    Resolution order:
    1) existing local path
    2) data/raw/<doc_name>
    3) recursive workspace search by file name
    """

    raw_input = doc_name_or_path.strip()
    if not raw_input:
        raise ValueError("Empty document input")

    maybe_path = Path(raw_input).expanduser()
    if maybe_path.exists() and maybe_path.is_file():
        if maybe_path.suffix.lower() != ".pdf":
            raise ValueError(f"Resolved path is not a PDF: {maybe_path}")
        return maybe_path.resolve()

    doc_name = _canonical_doc_name(raw_input)

    raw_candidate = (Path.cwd() / "data" / "raw" / doc_name)
    if raw_candidate.exists() and raw_candidate.is_file():
        return raw_candidate.resolve()

    matches: list[Path] = []
    for p in Path.cwd().rglob("*.pdf"):
        if p.name.lower() == doc_name.lower() and p.is_file():
            matches.append(p.resolve())

    if len(matches) == 1:
        return matches[0]

    if not matches:
        raise FileNotFoundError(
            f"Unable to locate PDF for '{doc_name}'. Checked direct path, data/raw, and recursive workspace search."
        )

    sample = "\n".join(f"- {m}" for m in matches[:10])
    raise ValueError(
        f"Multiple PDF matches found for '{doc_name}'. Please pass --pdf explicitly.\n{sample}"
    )


def _result_from_existing(
    doc_name: str,
    pdf_path: str | None = None,
    *,
    summary_built: bool = False,
) -> ProcessResult:
    config = get_doc_config(doc_name)
    if "error" in config:
        raise RuntimeError(f"Document is not registered: {doc_name}")

    chunks_dir = Path(str(config["chunks_dir"]))
    content_dir = Path(str(config["content_dir"]))
    doc_stem = _safe_doc_stem(Path(doc_name).stem)
    page_index_json = page_index_path_for_doc(doc_stem, chunks_dir)

    resolved_pdf = pdf_path or str(config.get("pdf_path", ""))
    if not resolved_pdf:
        resolved_pdf = doc_name

    return ProcessResult(
        doc_name=doc_name,
        doc_stem=doc_stem,
        pdf_path=resolved_pdf,
        page_index_json=str(page_index_json),
        chunks_dir=str(chunks_dir),
        content_dir=str(content_dir),
        total_pages=int(config["total_pages"]),
        index_built=False,
        structure_built=False,
        content_built=False,
        summary_built=summary_built,
        registered=False,
    )


def process_document(
    pdf_path: str,
    force: bool = False,
    model: str | None = None,
    toc_check_pages: int | None = None,
    max_pages_per_node: int | None = None,
    max_tokens_per_node: int | None = None,
    if_add_node_id: str | None = None,
    if_add_node_summary: str | None = None,
    if_add_node_text: str | None = None,
    if_add_doc_description: str | None = None,
    materialize_summaries: bool | None = None,
    preclassify_nodes: bool = False,
    classify_concurrency: int | None = None,
    structure_max_limit: int = 70000,
    content_chunk_size: int = 20,
    progress_callback: ProgressCallback | None = None,
) -> ProcessResult:
    """Process one PDF end-to-end and register it for QA."""
    source_pdf = Path(pdf_path).expanduser().resolve()
    try:
        if not source_pdf.exists() or not source_pdf.is_file():
            raise FileNotFoundError(f"PDF not found: {source_pdf}")
        if source_pdf.suffix.lower() != ".pdf":
            raise ValueError(f"Input must be a PDF: {source_pdf}")

        doc_name = _canonical_doc_name(source_pdf.name)
        _emit_progress(
            progress_callback,
            {"type": "stage_start", "stage": "ingest", "doc_name": doc_name},
        )

        project_root = Path.cwd().resolve()
        doc_stem = _safe_doc_stem(source_pdf.stem)

        chunks_dir = (project_root / chunk_dir_for_doc(doc_stem)).resolve()
        page_index_json = (project_root / page_index_path_for_doc(doc_stem)).resolve()
        content_root = (project_root / content_root_for_doc(doc_stem)).resolve()
        content_dir = content_root / "json"
        summary_requested = (
            bool(materialize_summaries)
            if materialize_summaries is not None
            else _flag_enabled(if_add_node_summary, default=True)
        )
        doc_description_requested = summary_requested and _flag_enabled(
            if_add_doc_description,
            default=False,
        )

        # Fast path: registered and all artifacts available
        if not force and is_document_processed(doc_name):
            summary_built = False
            if summary_requested:
                summary_built = _run_summary_materialization_stage(
                    doc_name=doc_name,
                    page_index_json=page_index_json,
                    content_dir=content_dir,
                    doc_root=_specindex_doc_root(project_root, doc_stem),
                    model=model,
                    include_doc_description=doc_description_requested,
                    progress_callback=progress_callback,
                )
                if summary_built:
                    _build_structure_chunks(
                        page_index_json=page_index_json,
                        chunks_dir=chunks_dir,
                        structure_max_limit=structure_max_limit,
                    )
            if preclassify_nodes:
                _run_preclassification_stage(
                    doc_name=doc_name,
                    doc_stem=doc_stem,
                    page_index_json=page_index_json,
                    content_dir=content_dir,
                    model=model,
                    classify_concurrency=classify_concurrency,
                    progress_callback=progress_callback,
                )
            logger.info("Document already processed, skipping rebuild: %s", doc_name)
            _emit_progress(
                progress_callback,
                {
                    "type": "stage_done",
                    "stage": "ingest",
                    "doc_name": doc_name,
                    "skipped": True,
                },
            )
            return _result_from_existing(doc_name, pdf_path=str(source_pdf), summary_built=summary_built)

        index_built = False
        structure_built = False
        content_built = False
        summary_built = False

        structure_needs_build = force or not _structure_ready(chunks_dir)
        content_needs_build = force or not _content_ready(content_dir)
        index_needs_build = force or not page_index_json.exists() or structure_needs_build

        _emit_progress(progress_callback, {"type": "stage_start", "stage": "index", "doc_name": doc_name})
        if index_needs_build:
            logger.info("[ingest] Building base index: %s", source_pdf)
            page_index = _load_page_index_builder()
            kwargs: dict[str, Any] = {}
            if model:
                kwargs["model"] = model
            if toc_check_pages is not None:
                kwargs["toc_check_page_num"] = toc_check_pages
            if max_pages_per_node is not None:
                kwargs["max_page_num_each_node"] = max_pages_per_node
            if max_tokens_per_node is not None:
                kwargs["max_token_num_each_node"] = max_tokens_per_node
            if if_add_node_id is not None:
                kwargs["if_add_node_id"] = if_add_node_id
            kwargs["if_add_node_summary"] = "no"
            if if_add_node_text is not None:
                kwargs["if_add_node_text"] = if_add_node_text
            kwargs["if_add_doc_description"] = "no"
            index_result = page_index(str(source_pdf), **kwargs)
            if not isinstance(index_result, dict) or "structure" not in index_result:
                raise RuntimeError("page_index returned invalid result: missing 'structure'")

            page_index_json.parent.mkdir(parents=True, exist_ok=True)
            page_index_json.write_text(
                json.dumps(index_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            index_built = True
        else:
            logger.info("[ingest] Reusing existing index JSON: %s", page_index_json)
        _emit_progress(
            progress_callback,
            {"type": "stage_done", "stage": "index", "doc_name": doc_name, "built": index_built},
        )

        _emit_progress(progress_callback, {"type": "stage_start", "stage": "content", "doc_name": doc_name})
        if content_needs_build:
            logger.info("[ingest] Building content DB: %s", content_dir)
            build_content_db = _load_content_builder()
            build_content_db(
                pdf_path=str(source_pdf),
                output_dir=str(content_root),
                chunk_size=content_chunk_size,
            )
            content_built = True
        else:
            logger.info("[ingest] Reusing existing content DB: %s", content_dir)
        _emit_progress(
            progress_callback,
            {"type": "stage_done", "stage": "content", "doc_name": doc_name, "built": content_built},
        )

        if not _content_ready(content_dir):
            raise RuntimeError(f"Content DB is missing or invalid: {content_dir}")

        total_pages = _read_total_pages_from_content_dir(content_dir)
        _emit_progress(progress_callback, {"type": "stage_start", "stage": "specindex_pages", "doc_name": doc_name})
        doc_root = _materialize_specindex_page_assets(
            project_root=project_root,
            source_pdf=source_pdf,
            doc_stem=doc_stem,
            content_dir=content_dir,
            progress_callback=progress_callback,
        )

        if summary_requested and not summary_built:
            summary_built = _run_summary_materialization_stage(
                doc_name=doc_name,
                page_index_json=page_index_json,
                content_dir=content_dir,
                doc_root=doc_root,
                model=model,
                include_doc_description=doc_description_requested,
                progress_callback=progress_callback,
            )

        _emit_progress(progress_callback, {"type": "stage_start", "stage": "chunk", "doc_name": doc_name})
        if structure_needs_build or summary_built:
            logger.info("[ingest] Building structure chunks: %s", chunks_dir)
            _build_structure_chunks(
                page_index_json=page_index_json,
                chunks_dir=chunks_dir,
                structure_max_limit=structure_max_limit,
            )
            structure_built = True
        else:
            logger.info("[ingest] Reusing existing structure chunks: %s", chunks_dir)
        _emit_progress(
            progress_callback,
            {"type": "stage_done", "stage": "chunk", "doc_name": doc_name, "built": structure_built},
        )

        if not _structure_ready(chunks_dir):
            raise RuntimeError(f"Structure chunks are missing or invalid: {chunks_dir}")

        if preclassify_nodes:
            _run_preclassification_stage(
                doc_name=doc_name,
                doc_stem=doc_stem,
                page_index_json=page_index_json,
                content_dir=content_dir,
                model=model,
                classify_concurrency=classify_concurrency,
                progress_callback=progress_callback,
            )

        chunks_dir_for_registry = _to_registry_path(chunks_dir, project_root)
        content_dir_for_registry = _to_registry_path(content_dir, project_root)
        pdf_path_for_registry = _to_registry_path(source_pdf, project_root)

        _emit_progress(progress_callback, {"type": "stage_start", "stage": "register", "doc_name": doc_name})
        logger.info("[ingest] Registering document: %s", doc_name)
        register_document(
            doc_name=doc_name,
            chunks_dir=chunks_dir_for_registry,
            content_dir=content_dir_for_registry,
            total_pages=total_pages,
            pdf_path=pdf_path_for_registry,
            persist=True,
        )
        _emit_progress(progress_callback, {"type": "stage_done", "stage": "register", "doc_name": doc_name, "built": True})

        result = ProcessResult(
            doc_name=doc_name,
            doc_stem=doc_stem,
            pdf_path=str(source_pdf),
            page_index_json=str(page_index_json),
            chunks_dir=chunks_dir_for_registry,
            content_dir=content_dir_for_registry,
            total_pages=total_pages,
            index_built=index_built,
            structure_built=structure_built,
            content_built=content_built,
            summary_built=summary_built,
            registered=True,
        )
        _emit_progress(
            progress_callback,
            {"type": "stage_done", "stage": "ingest", "doc_name": doc_name, "skipped": False},
        )
        return result
    except Exception as exc:
        _emit_progress(
            progress_callback,
            {
                "type": "error",
                "stage": "ingest",
                "message": str(exc),
                "doc_name": source_pdf.name if source_pdf.name else "",
            },
        )
        raise


def ensure_document_ready(
    doc: str | None = None,
    pdf: str | None = None,
    force: bool = False,
    model: str | None = None,
    toc_check_pages: int | None = None,
    max_pages_per_node: int | None = None,
    max_tokens_per_node: int | None = None,
    if_add_node_id: str | None = None,
    if_add_node_summary: str | None = None,
    if_add_node_text: str | None = None,
    if_add_doc_description: str | None = None,
    materialize_summaries: bool | None = None,
    structure_max_limit: int = 70000,
    content_chunk_size: int = 20,
    progress_callback: ProgressCallback | None = None,
) -> ProcessResult:
    """Ensure a document is processed and registered for QA."""

    if pdf:
        return process_document(
            pdf_path=pdf,
            force=force,
            model=model,
            toc_check_pages=toc_check_pages,
            max_pages_per_node=max_pages_per_node,
            max_tokens_per_node=max_tokens_per_node,
            if_add_node_id=if_add_node_id,
            if_add_node_summary=if_add_node_summary,
            if_add_node_text=if_add_node_text,
            if_add_doc_description=if_add_doc_description,
            materialize_summaries=materialize_summaries,
            preclassify_nodes=False,
            structure_max_limit=structure_max_limit,
            content_chunk_size=content_chunk_size,
            progress_callback=progress_callback,
        )

    if not doc:
        raise ValueError("Either doc or pdf must be provided")

    doc_name = _canonical_doc_name(doc)
    if not force and is_document_processed(doc_name):
        logger.info("Document already processed for QA: %s", doc_name)
        _emit_progress(
            progress_callback,
            {
                "type": "stage_done",
                "stage": "ensure_document_ready",
                "doc_name": doc_name,
                "skipped": True,
            },
        )
        return _result_from_existing(doc_name)

    resolved_pdf = resolve_pdf_for_doc(doc)
    return process_document(
        pdf_path=str(resolved_pdf),
        force=force,
        model=model,
        toc_check_pages=toc_check_pages,
        max_pages_per_node=max_pages_per_node,
        max_tokens_per_node=max_tokens_per_node,
        if_add_node_id=if_add_node_id,
        if_add_node_summary=if_add_node_summary,
        if_add_node_text=if_add_node_text,
        if_add_doc_description=if_add_doc_description,
        materialize_summaries=materialize_summaries,
        preclassify_nodes=False,
        structure_max_limit=structure_max_limit,
        content_chunk_size=content_chunk_size,
        progress_callback=progress_callback,
    )
