from __future__ import annotations

import asyncio

import utils


def test_summary_prompt_uses_navigation_index_with_asset_context():
    node = {
        "node_id": "n1",
        "title": "3.1 Packet Layout",
        "start_index": 4,
        "end_index": 5,
        "text": "This section defines the packet layout and Status field.",
        "_summary_assets": {
            "tables": [
                {
                    "asset_id": "table_0001",
                    "caption": "Table 1 Packet Header",
                    "pages": [4],
                    "row_count": 12,
                    "cell_count": 36,
                    "preview": "Header: Field | Width | Description",
                }
            ],
            "figures": [
                {
                    "asset_id": "figure_0001",
                    "caption": "Figure 1 State Flow",
                    "pages": [5],
                }
            ],
        },
    }

    prompt = utils._build_node_summary_prompt(node)

    assert "NAVIGATION INDEX" in prompt
    assert "Return 80-140 words" in prompt
    assert "Use only the provided section text, tables, and figures" in prompt
    assert "Tables in this section:" in prompt
    assert "table_0001" in prompt
    assert "Table 1 Packet Header" in prompt
    assert "Header: Field | Width | Description" in prompt
    assert "Figures in this section:" in prompt
    assert "Figure 1 State Flow" in prompt


def test_summary_cache_key_includes_asset_context(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTOCOL_TWIN_SUMMARY_CACHE_DIR", str(tmp_path / "summary-cache"))
    base = {"node_id": "n1", "text": "Same section text."}
    with_table = {
        **base,
        "_summary_assets": {
            "tables": [{"asset_id": "table_0001", "caption": "Table 1 A", "pages": [1]}],
            "figures": [],
        },
    }
    with_other_table = {
        **base,
        "_summary_assets": {
            "tables": [{"asset_id": "table_0002", "caption": "Table 2 B", "pages": [1]}],
            "figures": [],
        },
    }

    assert utils._summary_cache_path(with_table, model="test-model") != utils._summary_cache_path(
        with_other_table,
        model="test-model",
    )


def test_read_summary_cache_rejects_raw_sse_payload(tmp_path):
    cache_path = tmp_path / "bad.json"
    cache_path.write_text(
        '{"summary": "data: {\\"type\\":\\"response.created\\"}\\n\\ndata: [DONE]"}',
        encoding="utf-8",
    )

    assert utils._read_summary_cache(cache_path) is None


def test_read_summary_cache_strips_leading_think_block(tmp_path):
    cache_path = tmp_path / "think.json"
    cache_path.write_text(
        '{"summary": "<think>private reasoning</think>\\n\\nCore topic: Packet format."}',
        encoding="utf-8",
    )

    assert utils._read_summary_cache(cache_path) == "Core topic: Packet format."


def test_generated_summary_sanitizes_before_cache_write(tmp_path, monkeypatch):
    calls: list[str] = []

    async def fake_chatgpt_api_async(model, prompt, **_kwargs):
        calls.append(prompt)
        return "<think>do not persist this</think>\n\nCore topic: Clean index."

    monkeypatch.setenv("PROTOCOL_TWIN_SUMMARY_CACHE_DIR", str(tmp_path / "summary-cache"))
    monkeypatch.setattr(utils, "ChatGPT_API_async", fake_chatgpt_api_async)
    nodes = [{"node_id": "n1", "text": "section"}]

    asyncio.run(utils.generate_summaries_for_nodes(nodes, model="test-model", concurrency=1))

    assert nodes[0]["summary"] == "Core topic: Clean index."
    cache_files = list((tmp_path / "summary-cache").glob("*.json"))
    assert len(cache_files) == 1
    payload = cache_files[0].read_text(encoding="utf-8")
    assert "<think>" not in payload
    assert "Core topic: Clean index." in payload
    assert len(calls) == 1


def test_generate_summaries_reuses_persistent_cache(tmp_path, monkeypatch):
    calls: list[tuple[str | None, str]] = []

    async def fake_chatgpt_api_async(model, prompt, **_kwargs):
        calls.append((model, prompt))
        return f"cached summary {len(calls)}"

    monkeypatch.setenv("PROTOCOL_TWIN_SUMMARY_CACHE_DIR", str(tmp_path / "summary-cache"))
    monkeypatch.setattr(utils, "ChatGPT_API_async", fake_chatgpt_api_async)

    first = [{"node_id": "n1", "text": "The same section text."}]
    second = [{"node_id": "n1-copy", "text": "The same section text."}]

    asyncio.run(utils.generate_summaries_for_structure(first, model="test-model", concurrency=1))
    asyncio.run(utils.generate_summaries_for_structure(second, model="test-model", concurrency=1))

    assert first[0]["summary"] == "cached summary 1"
    assert second[0]["summary"] == "cached summary 1"
    assert len(calls) == 1
    assert list((tmp_path / "summary-cache").glob("*.json"))
