"""Node-level search tool for PageIndex-style document navigation."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from src.extract.content_loader import get_node_pages, get_node_text
from src.tools.registry import get_doc_config

MAX_LIMIT = 25
DEFAULT_LIMIT = 8
TEXT_PREVIEW_CHARS = 240
MAX_INDEX_TEXT_CHARS = 40000

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*|[\u4e00-\u9fff]", re.IGNORECASE)

_EXPANSION_RULES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("帧", "报文", "数据包", "包", "消息", "分组", "pdu"), ("frame", "packet", "message", "pdu", "datagram", "segment")),
    (("结构", "格式", "format"), ("structure", "format", "header")),
    (("字段", "域", "field"), ("field", "fields", "header")),
    (("类型", "type", "种类"), ("type", "kind", "flag", "flags", "option", "control")),
    (("机制", "原理", "工作机制", "功能", "主要功能"), ("mechanism", "mechanisms", "overview", "introduction", "concept", "concepts", "operation", "functional specification")),
    (("状态机", "状态转换", "状态图", "state machine"), ("state", "states", "state machine", "transition", "transitions", "lifecycle")),
    (("实现", "怎么实现", "处理", "流程", "过程", "procedure"), ("implementation", "processing", "event processing", "procedure", "operation", "algorithm")),
    (("iso", "osi", "第几层", "哪一层", "网络层次", "分层"), ("iso", "osi", "layer", "layers", "transport", "network", "link", "application", "purpose", "scope")),
]

_INTENT_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...], float]] = [
    ("message_format", ("帧", "报文", "数据包", "包", "消息", "字段", "格式", "结构", "type", "类型", "field", "format"), ("header", "format", "field", "fields", "option", "message format", "packet format", "frame format", "pdu format"), 36.0),
    ("overview_mechanisms", ("机制", "原理", "概览", "有什么", "功能", "overview", "mechanism"), ("introduction", "key concept", "concept", "functional specification", "overview", "operation", "mechanism", "architecture"), 24.0),
    ("state_machine", ("状态机", "状态转换", "状态图", "state machine", "state transition"), ("state machine", "states", "transition", "lifecycle"), 36.0),
    ("implementation_flow", ("实现", "怎么实现", "具体怎么", "处理", "流程", "过程", "procedure", "implementation"), ("event processing", "processing", "procedure", "operation", "algorithm", "implementation"), 34.0),
    ("network_layer", ("iso", "osi", "第几层", "哪一层", "层", "layer"), ("purpose", "scope", "introduction", "layer", "transport", "network", "lower-level", "interface"), 28.0),
]


def search_nodes(doc_name: str, query: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return ranked document nodes likely to contain evidence for ``query``.

    This is a deterministic first-hop recall tool. It ranks PageIndex nodes by
    weighted lexical matches across title path, summary, and node text. The
    agent should still call ``get_page_content`` for authoritative evidence.
    """

    doc_name = str(doc_name or "").strip()
    query = str(query or "").strip()
    if not doc_name:
        return {"error": "doc_name is required."}
    if not query:
        return {"error": "query is required."}

    config = get_doc_config(doc_name)
    if "error" in config:
        return config

    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = DEFAULT_LIMIT
    limit_int = max(1, min(MAX_LIMIT, limit_int))

    chunks_dir = str(config["chunks_dir"])
    content_dir = str(config["content_dir"])
    records = _load_node_records(chunks_dir, content_dir)
    if not records:
        return {"doc_name": doc_name, "query": query, "results": [], "next_steps": "No searchable nodes found."}

    expanded_query, intents = _expand_query(query)
    query_tokens = _tokenize(expanded_query)
    if not query_tokens:
        return {"doc_name": doc_name, "query": query, "results": [], "next_steps": "No searchable query terms found."}

    document_frequency = _document_frequency(records)
    node_count = len(records)
    scored: list[dict[str, Any]] = []
    for record in records:
        score_info = _score_record(record, expanded_query, query_tokens, intents, document_frequency, node_count)
        if score_info["score"] <= 0:
            continue
        scored.append({**record, **score_info})

    scored.sort(key=lambda item: (-float(item["score"]), item["start_index"], item["node_id"]))
    results = [_result_item(item) for item in scored[:limit_int]]
    return {
        "doc_name": doc_name,
        "query": query,
        "expanded_query": expanded_query,
        "intents": intents,
        "limit": limit_int,
        "result_count": len(results),
        "results": results,
        "next_steps": (
            "Use node_id/title_path/pages to choose evidence candidates, then call "
            "get_page_content on the returned pages before answering."
        ),
    }


def _load_node_records(chunks_dir: str, content_dir: str) -> list[dict[str, Any]]:
    nodes = _load_flat_nodes(chunks_dir)
    records: list[dict[str, Any]] = []
    for node, title_path in nodes:
        pages = get_node_pages(node)
        if not pages:
            continue
        title = str(node.get("title") or "")
        summary = str(node.get("summary") or "")
        text = get_node_text(node, content_dir) or ""
        text = text[:MAX_INDEX_TEXT_CHARS]
        records.append(
            {
                "node_id": str(node.get("node_id") or ""),
                "title": title,
                "title_path": title_path,
                "summary": summary,
                "text": text,
                "pages": pages,
                "start_index": pages[0],
                "end_index": pages[-1],
                "title_tokens": Counter(_tokenize(" ".join(title_path))),
                "summary_tokens": Counter(_tokenize(summary)),
                "text_tokens": Counter(_tokenize(text)),
            }
        )
    return records


def _load_flat_nodes(chunks_dir: str) -> list[tuple[dict[str, Any], list[str]]]:
    chunks_path = Path(chunks_dir)
    if not chunks_path.exists():
        return []

    nodes: list[tuple[dict[str, Any], list[str]]] = []
    for path in _part_files(chunks_path):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        structure = payload.get("structure", [])
        if isinstance(structure, list):
            _append_flat_nodes(structure, [], nodes)
    return nodes


def _part_files(chunks_path: Path) -> list[Path]:
    manifest_path = chunks_path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        files = manifest.get("files", [])
        if isinstance(files, list):
            existing = [chunks_path / str(name) for name in files if (chunks_path / str(name)).exists()]
            if existing:
                return existing
    page_index_path = chunks_path / "page_index.json"
    if page_index_path.exists():
        return [page_index_path]
    return sorted(chunks_path.glob("part_*.json"))


def _append_flat_nodes(
    items: list[Any],
    parent_path: list[str],
    out: list[tuple[dict[str, Any], list[str]]],
) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        title_path = parent_path + ([title] if title else [])
        out.append((item, title_path))
        children = item.get("children", [])
        if isinstance(children, list):
            _append_flat_nodes(children, title_path, out)


def _tokenize(text: str) -> list[str]:
    raw_tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(str(text or ""))]
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.append(token)
        if any(sep in token for sep in (".", "_", "+", "-")):
            tokens.extend(part for part in re.split(r"[._+-]+", token) if len(part) >= 2)
    return tokens


def _expand_query(query: str) -> tuple[str, list[str]]:
    text = str(query or "")
    lowered = text.lower()
    additions: list[str] = []
    for triggers, expansions in _EXPANSION_RULES:
        if any(trigger.lower() in lowered for trigger in triggers):
            additions.extend(expansions)

    intents: list[str] = []
    for name, triggers, _title_terms, _weight in _INTENT_RULES:
        if any(trigger.lower() in lowered for trigger in triggers):
            intents.append(name)

    deduped_additions = _dedupe_preserve_order(additions)
    expanded = " ".join([text, *deduped_additions]).strip()
    return expanded, intents


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _document_frequency(records: list[dict[str, Any]]) -> Counter[str]:
    df: Counter[str] = Counter()
    for record in records:
        unique = set(record["title_tokens"]) | set(record["summary_tokens"]) | set(record["text_tokens"])
        df.update(unique)
    return df


def _idf(token: str, document_frequency: Counter[str], node_count: int) -> float:
    return math.log((node_count + 1) / (document_frequency.get(token, 0) + 1)) + 1.0


def _score_record(
    record: dict[str, Any],
    query: str,
    query_tokens: list[str],
    intents: list[str],
    document_frequency: Counter[str],
    node_count: int,
) -> dict[str, Any]:
    title_score = 0.0
    summary_score = 0.0
    text_score = 0.0
    matched_terms: set[str] = set()

    for token in query_tokens:
        idf = _idf(token, document_frequency, node_count)
        title_hits = record["title_tokens"].get(token, 0)
        summary_hits = record["summary_tokens"].get(token, 0)
        text_hits = record["text_tokens"].get(token, 0)
        if title_hits or summary_hits or text_hits:
            matched_terms.add(token)
        title_score += min(title_hits, 3) * idf * 5.0
        summary_score += min(summary_hits, 5) * idf * 2.0
        text_score += min(text_hits, 10) * idf * 0.55

    phrase_bonus = _phrase_bonus(record, query)
    intent_bonus = _intent_bonus(record, intents)
    score = title_score + summary_score + text_score + phrase_bonus + intent_bonus
    return {
        "score": round(score, 4),
        "score_breakdown": {
            "title": round(title_score, 4),
            "summary": round(summary_score, 4),
            "text": round(text_score, 4),
            "phrase": round(phrase_bonus, 4),
            "intent": round(intent_bonus, 4),
        },
        "matched_terms": sorted(matched_terms),
    }


def _phrase_bonus(record: dict[str, Any], query: str) -> float:
    normalized_query = _normalize_phrase(query)
    if not normalized_query:
        return 0.0
    title_path = _normalize_phrase(" ".join(record["title_path"]))
    text = _normalize_phrase(record["text"])
    bonus = 0.0
    if normalized_query in title_path:
        bonus += 8.0
    elif any(part and part in title_path for part in normalized_query.split() if len(part) >= 4):
        bonus += 2.0
    if normalized_query in text:
        bonus += 3.0
    return bonus


def _intent_bonus(record: dict[str, Any], intents: list[str]) -> float:
    if not intents:
        return 0.0
    title = _normalize_phrase(str(record.get("title") or ""))
    title_path = _normalize_phrase(" ".join(record["title_path"]))
    text = _normalize_phrase(record["text"][:3000])
    score = 0.0
    for name, _triggers, title_terms, weight in _INTENT_RULES:
        if name not in intents:
            continue
        current_title_hits = sum(1 for term in title_terms if _normalize_phrase(term) in title)
        path_hits = sum(1 for term in title_terms if _normalize_phrase(term) in title_path)
        text_hits = sum(1 for term in title_terms if _normalize_phrase(term) in text)
        if current_title_hits:
            score += weight + min(current_title_hits - 1, 3) * 4.0
        elif path_hits:
            score += weight * 0.55 + min(path_hits - 1, 3) * 2.0
        elif text_hits:
            score += weight * 0.45 + min(text_hits - 1, 3) * 2.0
        score += _intent_shape_bonus(record, name)
    return score


def _intent_shape_bonus(record: dict[str, Any], intent: str) -> float:
    depth = len(record.get("title_path") or [])
    title = _normalize_phrase(str(record.get("title") or ""))
    if intent == "overview_mechanisms":
        bonus = 0.0
        if "appendix" in title or "reference" in title:
            bonus -= 12.0
        if "key concept" in title or "concept" in title:
            bonus += 8.0
        if "functional specification" in title and depth <= 1:
            bonus += 12.0
        if "terminology" in title:
            bonus -= 8.0
        if depth <= 1:
            return bonus + 18.0
        if depth == 2:
            return bonus + 12.0
        if depth == 3:
            return bonus - 6.0
        return bonus - 10.0
    if intent == "implementation_flow":
        if any(term in title for term in ("event processing", "processing", "procedure", "implementation")):
            return 12.0
        if depth >= 4:
            return -4.0
    if intent == "network_layer":
        if any(term in title for term in ("purpose", "scope", "interface", "lower level", "lower-level", "layer")):
            return 8.0
    return 0.0


def _normalize_phrase(text: str) -> str:
    return " ".join(_tokenize(text))


def _result_item(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get("text") or "")
    preview = " ".join(text.split())[:TEXT_PREVIEW_CHARS]
    return {
        "node_id": item["node_id"],
        "title": item["title"],
        "title_path": item["title_path"],
        "pages": item["pages"],
        "page_range": f"{item['start_index']}-{item['end_index']}",
        "score": item["score"],
        "score_breakdown": item["score_breakdown"],
        "matched_terms": item["matched_terms"],
        "preview": preview,
    }
