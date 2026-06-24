"""Helpers for loading node text from page_index nodes and Content DB."""

from __future__ import annotations

import logging
from pathlib import Path
import re

from src.tools.page_content import _load_page_data

logger = logging.getLogger("extract")

_ASCII_LAYOUT_LINE_RE = re.compile(r"(<[-=]+|[-=]+>|[-=]{5,}|[+|][\-+| ]{2,}|[/\\^v])")
_MULTISPACE_RE = re.compile(r" {2,}")
LAYOUT_SENSITIVE_TEXT_MARKER = "[layout-sensitive ASCII figure text; preserve spacing]"


def get_node_pages(node: dict) -> list[int]:
    """Return the inclusive page span for a node."""
    start_index = node.get("start_index")
    end_index = node.get("end_index")
    if not isinstance(start_index, int) or not isinstance(end_index, int):
        return []
    if start_index <= 0 or end_index < start_index:
        return []
    return list(range(start_index, end_index + 1))


def _slice_lines(text: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Slice 1-based inclusive line ranges from a page text block."""
    if not text:
        return ""

    lines = text.splitlines()
    if not lines:
        return ""

    start = 1 if not isinstance(start_line, int) or start_line < 1 else start_line
    end = len(lines) if not isinstance(end_line, int) or end_line < 1 else end_line

    start = min(start, len(lines))
    end = min(end, len(lines))
    if end < start:
        return ""
    return "\n".join(lines[start - 1 : end])


def _ascii_layout_score(text: str) -> int:
    score = 0
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        symbol_count = sum(1 for char in stripped if char in "|+-<>/^\\")
        if symbol_count >= 3 and _ASCII_LAYOUT_LINE_RE.search(stripped):
            score += 1
    return score


def _max_space_run(text: str) -> int:
    runs = [len(match.group(0)) for match in _MULTISPACE_RE.finditer(text or "")]
    return max(runs, default=0)


def select_page_text_with_metadata(page: dict, *, allow_layout_text: bool) -> tuple[str, bool]:
    """Return page text and whether layout-preserving text was selected."""
    text = page.get("text", "")
    layout_text = page.get("layout_text", "")
    if not allow_layout_text or not isinstance(layout_text, str) or not layout_text.strip():
        return text if isinstance(text, str) else "", False
    if not isinstance(text, str):
        return layout_text, True

    layout_score = _ascii_layout_score(layout_text)
    if layout_score < 4:
        return text, False
    if _max_space_run(layout_text) <= _max_space_run(text):
        return text, False
    return layout_text, True


def select_page_text(page: dict, *, allow_layout_text: bool) -> str:
    """Return regular prose text or layout-preserving text for ASCII diagrams."""
    text, _ = select_page_text_with_metadata(page, allow_layout_text=allow_layout_text)
    return text


def get_node_text(node: dict, content_dir: str) -> str | None:
    """Get the text content for a leaf node."""
    direct_text = node.get("text")
    if isinstance(direct_text, str) and direct_text != "":
        return direct_text

    page_nums = get_node_pages(node)
    if not page_nums:
        logger.error("Node %s has no valid page span", node.get("node_id", "<unknown>"))
        return None

    content_path = Path(content_dir)
    if not content_path.exists():
        logger.error(
            "Content DB missing for node %s: %s",
            node.get("node_id", "<unknown>"),
            content_dir,
        )
        return None

    page_data = _load_page_data(str(content_path), page_nums)
    missing_pages = [page_num for page_num in page_nums if page_num not in page_data]
    if missing_pages:
        logger.error(
            "Content DB pages missing for node %s: %s",
            node.get("node_id", "<unknown>"),
            missing_pages,
        )
        return None

    start_index = node["start_index"]
    end_index = node["end_index"]
    start_line = node.get("start_line")
    end_line = node.get("end_line")
    allow_layout_text = not isinstance(start_line, int) and not isinstance(end_line, int)

    parts: list[str] = []
    for page_num in page_nums:
        text = select_page_text(page_data[page_num], allow_layout_text=allow_layout_text)
        if page_num == start_index and page_num == end_index:
            chunk = _slice_lines(text, start_line, end_line)
        elif page_num == start_index:
            chunk = _slice_lines(text, start_line, None)
        elif page_num == end_index:
            chunk = _slice_lines(text, 1, end_line)
        else:
            chunk = text
        if chunk:
            parts.append(chunk)

    if not parts:
        return None
    return "\n".join(parts)


def get_node_layout_text(node: dict, content_dir: str) -> str | None:
    """Get layout-preserving full-page text for figure/table sidecars.

    Unlike get_node_text(), this intentionally ignores start_line/end_line
    slicing because line ranges from regular text extraction do not reliably
    align with layout-preserving ASCII diagrams.
    """

    page_nums = get_node_pages(node)
    if not page_nums:
        logger.error("Node %s has no valid page span", node.get("node_id", "<unknown>"))
        return None

    content_path = Path(content_dir)
    if not content_path.exists():
        logger.error(
            "Content DB missing for node %s: %s",
            node.get("node_id", "<unknown>"),
            content_dir,
        )
        return None

    page_data = _load_page_data(str(content_path), page_nums)
    missing_pages = [page_num for page_num in page_nums if page_num not in page_data]
    if missing_pages:
        logger.error(
            "Content DB pages missing for node %s: %s",
            node.get("node_id", "<unknown>"),
            missing_pages,
        )
        return None

    parts: list[str] = []
    for page_num in page_nums:
        page = page_data[page_num]
        layout_text = page.get("layout_text", "")
        text = page.get("text", "")
        if isinstance(layout_text, str) and layout_text.strip():
            parts.append(layout_text)
        elif isinstance(text, str) and text:
            parts.append(text)
    parts = [part for part in parts if part]
    if not parts:
        return None
    return "\n".join(parts)
