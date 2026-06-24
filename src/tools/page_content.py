"""Page content tool for retrieving document page content."""

import json
from pathlib import Path
from typing import Any

from .registry import get_doc_config

MAX_PAGES_PER_REQUEST = 10
TEXT_TRUNCATE_LIMIT = 4000
PROCESSED_SPECS_DIR = "processed_specs"


def parse_pages(pages_str: str) -> list[int]:
    """
    Parse a pages string into a sorted list of page numbers.

    Supported formats:
        - Single page: "7"
        - Range: "7-11"
        - Comma-separated: "7,9,11"
        - Mixed comma-separated pages/ranges: "36,166-170,179,203"

    Args:
        pages_str: Page specification string.

    Returns:
        Sorted list of integer page numbers.

    Raises:
        ValueError: If the format is invalid.
    """
    if not isinstance(pages_str, str):
        raise TypeError("pages string must be a string")

    pages_str = pages_str.strip()
    if not pages_str:
        raise ValueError("Empty pages string")

    pages: set[int] = set()
    for token in pages_str.split(","):
        part = token.strip()
        if not part:
            raise ValueError(f"Invalid pages format: {pages_str}")

        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if start > end:
                raise ValueError(f"Invalid range: {start} > {end}")
            pages.update(range(start, end + 1))
            continue

        pages.add(int(part))

    return sorted(pages)


def _truncate_text(text: str, limit: int = TEXT_TRUNCATE_LIMIT) -> str:
    """
    Truncate text at a paragraph boundary if it exceeds the limit.

    Looks for the last double-newline before the limit to preserve paragraph integrity.
    Falls back to the last single newline if no paragraph break is found.

    Args:
        text: The text to potentially truncate.
        limit: Maximum character count.

    Returns:
        Original text if within limit, or truncated text with annotation.
    """
    if len(text) <= limit:
        return text

    total_len = len(text)
    # Try to find a paragraph boundary (double newline) before the limit
    cut_point = text.rfind("\n\n", 0, limit)
    if cut_point == -1:
        # Fall back to single newline
        cut_point = text.rfind("\n", 0, limit)
    if cut_point == -1:
        # No newline found, hard cut at limit
        cut_point = limit

    truncated = text[:cut_point]
    return truncated + f"\n\n[内容已截断，共 {total_len} 字符，已显示前 {len(truncated)} 字符]"


def _load_page_data(content_dir: str, page_nums: list[int]) -> dict[int, dict]:
    """
    Load page data from content JSON files in the content directory.

    Scans content_{start}_{end}.json files to find pages matching requested page numbers.

    Args:
        content_dir: Path to the directory containing content JSON files.
        page_nums: List of page numbers to load.

    Returns:
        Dictionary mapping page number to page data dict.
    """
    needed = set(page_nums)
    found: dict[int, dict] = {}

    content_path = Path(content_dir)
    if not content_path.exists():
        return found

    for fname in sorted(content_path.iterdir()):
        if not fname.name.endswith(".json") or not fname.name.startswith("content_"):
            continue

        # Parse start and end from filename: content_{start}_{end}.json
        stem = fname.stem  # e.g. "content_1_20"
        parts = stem.split("_")
        if len(parts) < 3:
            continue
        try:
            file_start = int(parts[1])
            file_end = int(parts[2])
        except ValueError:
            continue

        # Check if any needed pages fall in this file's range
        if not any(file_start <= p <= file_end for p in needed):
            continue

        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        for page in data.get("pages", []):
            pnum = page.get("page_num")
            if pnum in needed:
                found[pnum] = page
                needed.discard(pnum)

        if not needed:
            break

    return found


def _candidate_processed_roots() -> list[Path]:
    roots = [Path.cwd() / PROCESSED_SPECS_DIR]
    project_root = Path(__file__).resolve().parents[2]
    project_processed = project_root / PROCESSED_SPECS_DIR
    if project_processed not in roots:
        roots.append(project_processed)
    return roots


def _resolve_specindex_doc_root(doc_name: str) -> Path | None:
    candidates = [doc_name]
    stem = Path(doc_name).stem
    if stem not in candidates:
        candidates.append(stem)

    for processed_root in _candidate_processed_roots():
        if not processed_root.exists():
            continue
        for doc_id in candidates:
            for candidate in processed_root.glob(f"*/{doc_id}"):
                if candidate.is_dir():
                    return candidate
    return None


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _specindex_total_pages(doc_root: Path) -> int:
    max_page = 0
    for text_path in sorted((doc_root / "pages").glob("page_*/text.json")):
        payload = _read_json_if_exists(text_path)
        if isinstance(payload, dict):
            try:
                max_page = max(max_page, int(payload.get("page", 0)))
            except (TypeError, ValueError):
                pass
        try:
            max_page = max(max_page, int(text_path.parent.name.rsplit("_", 1)[1]))
        except (IndexError, ValueError):
            pass
    return max_page


def _get_specindex_page_content(doc_root: Path, page_nums: list[int]) -> dict[str, Any]:
    total_pages = _specindex_total_pages(doc_root)
    out_of_range = [p for p in page_nums if p < 1 or (total_pages and p > total_pages)]
    if out_of_range:
        return {
            "error": f"Pages out of range: {out_of_range}",
            "valid_range": f"1-{total_pages}",
        }

    content: list[dict[str, Any]] = []
    for pnum in page_nums:
        page_dir = doc_root / "pages" / f"page_{pnum:03d}"
        text_path = page_dir / "text.json"
        payload = _read_json_if_exists(text_path)
        if not isinstance(payload, dict):
            content.append(
                {
                    "page": pnum,
                    "text": f"[Page {pnum} data not found in processed_specs]",
                    "text_spans": [],
                    "asset_refs": [],
                    "page_image_path": str(page_dir / "page.png"),
                    "metadata": {
                        "source": "processed_specs",
                        "doc_id": doc_root.name,
                        "text_path": str(text_path),
                    },
                }
            )
            continue

        spans = payload.get("spans", [])
        text = "\n".join(
            span.get("text", "")
            for span in spans
            if isinstance(span, dict) and isinstance(span.get("text"), str)
        )
        content.append(
            {
                "page": payload.get("page", pnum),
                "text": _truncate_text(text),
                "text_spans": spans if isinstance(spans, list) else [],
                "asset_refs": payload.get("asset_ids", []),
                "page_image_path": str(page_dir / "page.png"),
                "metadata": {
                    "source": "processed_specs",
                    "doc_id": doc_root.name,
                    "text_path": str(text_path),
                },
            }
        )

    return {
        "content": content,
        "next_steps": (
            "Use span_id refs for text claims. If asset_refs contains table or figure "
            "ids, call list_assets plus get_table/get_image before claiming table or "
            "figure facts."
        ),
        "total_pages": total_pages,
    }


def get_page_content(doc_name: str, pages: str) -> dict[str, Any]:
    """
    Get the content of specified pages from a document.

    Args:
        doc_name: Document name, e.g., "FC-LS.pdf"
        pages: Page specification string. Supports:
               - Single page: "7"
               - Range: "7-11"
               - Comma-separated: "7,9,11"
               - Mixed comma-separated pages/ranges: "36,166-170,179,203"

    Returns:
        Dictionary containing:
        - content: List of page dicts with page, text, tables, images
        - next_steps: Navigation hint with citation format
        - total_pages: Total pages in the document

        Or error dictionary on failure.
    """
    # Parse pages
    try:
        page_nums = parse_pages(pages)
    except (ValueError, TypeError):
        return {"error": f"Invalid pages format: {pages}. Use '7', '7-11', '7,9,11', or '36,166-170,179,203'."}

    if not page_nums:
        return {"error": f"Invalid pages format: {pages}. Use '7', '7-11', '7,9,11', or '36,166-170,179,203'."}

    # Check page count limit
    if len(page_nums) > MAX_PAGES_PER_REQUEST:
        return {"error": f"Too many pages ({len(page_nums)}, max {MAX_PAGES_PER_REQUEST}). Please request fewer pages."}

    specindex_root = _resolve_specindex_doc_root(doc_name)
    if specindex_root is not None:
        return _get_specindex_page_content(specindex_root, page_nums)

    # Validate document
    config = get_doc_config(doc_name)
    if "error" in config:
        return config

    total_pages = config["total_pages"]
    content_dir = config["content_dir"]

    # Check page range
    out_of_range = [p for p in page_nums if p < 1 or p > total_pages]
    if out_of_range:
        return {
            "error": f"Pages out of range: {out_of_range}",
            "valid_range": f"1-{total_pages}",
        }

    # Load page data
    page_data = _load_page_data(content_dir, page_nums)

    # Build response content
    content = []
    for pnum in page_nums:
        raw = page_data.get(pnum)
        if raw is None:
            content.append({
                "page": pnum,
                "text": f"[Page {pnum} data not found in content files]",
                "tables": [],
                "images": [],
            })
            continue

        text = raw.get("text", "")
        text = _truncate_text(text)

        content.append({
            "page": raw.get("page_num", pnum),
            "text": text,
            "tables": raw.get("tables", []),
            "images": raw.get("images", []),
        })

    return {
        "content": content,
        "next_steps": (
            f'Use <cite doc="{doc_name}" page="N"/> to cite information from these pages.'
        ),
        "total_pages": total_pages,
    }
