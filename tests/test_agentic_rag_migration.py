from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.agent import loop
from src.ingest import pipeline
from src.models import LLMResponse, TokenUsage, ToolCall
from src.tools.registry import get_doc_config, is_document_processed
from src.web.app import app


def _write_dummy_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n%v7 smoke\n")


def _write_text_pdf(path: Path, text: str = "Demo Packet Version") -> None:
    import fitz

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _write_asset_pdf(path: Path) -> None:
    import fitz

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=360, height=360)
    page.insert_text((36, 30), "Table 1 Demo Packet Format")

    x0, y0 = 36, 56
    col_w, row_h = 96, 28
    for i in range(3):
        y = y0 + i * row_h
        page.draw_line((x0, y), (x0 + 2 * col_w, y))
    for i in range(3):
        x = x0 + i * col_w
        page.draw_line((x, y0), (x, y0 + 2 * row_h))
    page.insert_text((x0 + 8, y0 + 18), "Field")
    page.insert_text((x0 + col_w + 8, y0 + 18), "Width")
    page.insert_text((x0 + 8, y0 + row_h + 18), "Version")
    page.insert_text((x0 + col_w + 8, y0 + row_h + 18), "3 bits")

    page.insert_text((36, 150), "Figure 1 Demo State")
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16), False)
    pix.clear_with(0x00FF00)
    page.insert_image(fitz.Rect(36, 170, 92, 226), stream=pix.tobytes("png"))
    doc.save(path)
    doc.close()


def _draw_simple_table(page, *, x0: int, y0: int, row_values: list[tuple[str, str]]) -> None:
    col_w, row_h = 96, 28
    row_count = len(row_values) + 1
    for i in range(row_count + 1):
        y = y0 + i * row_h
        page.draw_line((x0, y), (x0 + 2 * col_w, y))
    for i in range(3):
        x = x0 + i * col_w
        page.draw_line((x, y0), (x, y0 + row_count * row_h))
    page.insert_text((x0 + 8, y0 + 18), "Field")
    page.insert_text((x0 + col_w + 8, y0 + 18), "Width")
    for row_index, (field, width) in enumerate(row_values, start=1):
        y = y0 + row_index * row_h
        page.insert_text((x0 + 8, y + 18), field)
        page.insert_text((x0 + col_w + 8, y + 18), width)


def _write_two_page_continuation_table_pdf(path: Path) -> None:
    import fitz

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page1 = doc.new_page(width=360, height=240)
    page1.insert_text((36, 30), "Table 1 Demo Packet Format")
    _draw_simple_table(page1, x0=36, y0=56, row_values=[("Version", "3 bits")])

    page2 = doc.new_page(width=360, height=240)
    page2.insert_text((36, 30), "Table 1 Demo Packet Format continued")
    _draw_simple_table(page2, x0=36, y0=56, row_values=[("Payload", "variable")])
    doc.save(path)
    doc.close()


def _install_fake_ingest_builders(monkeypatch, total_pages: int = 2) -> None:
    def fake_page_index(pdf_path: str, **_kwargs):
        return {
            "doc_name": Path(pdf_path).name,
            "structure": [
                {
                    "node_id": "0001",
                    "title": "Test Section",
                    "start_index": 1,
                    "end_index": 1,
                }
            ],
        }

    def fake_load_root(page_index_json: str):
        payload = json.loads(Path(page_index_json).read_text(encoding="utf-8"))
        return "ROOT", str(payload.get("doc_name", "unknown.pdf"))

    def fake_chunk(root_node, doc_name: str, max_limit: int):
        return [
            {
                "success": True,
                "doc_name": doc_name,
                "structure": [
                    {
                        "node_id": "0001",
                        "title": "Test Section",
                        "start_index": 1,
                        "end_index": 1,
                    }
                ],
            }
        ]

    def fake_save_parts(parts, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "part_0001.json").write_text(
            json.dumps(parts[0], ensure_ascii=False),
            encoding="utf-8",
        )
        (output_dir / "manifest.json").write_text(
            json.dumps({"total_parts": 1, "files": ["part_0001.json"]}),
            encoding="utf-8",
        )

    def fake_content_builder(pdf_path: str, output_dir: str, chunk_size: int = 20):
        json_dir = Path(output_dir) / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        out = json_dir / f"content_1_{total_pages}.json"
        out.write_text(
            json.dumps(
                {
                    "doc_name": Path(pdf_path).name,
                    "start_page": 1,
                    "end_page": total_pages,
                    "pages": [
                        {"page_num": page, "text": f"page {page}", "tables": [], "images": []}
                        for page in range(1, total_pages + 1)
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return [out]

    monkeypatch.setattr(pipeline, "_load_page_index_builder", lambda: fake_page_index)
    monkeypatch.setattr(
        pipeline,
        "_load_structure_helpers",
        lambda: (fake_load_root, fake_chunk, fake_save_parts),
    )
    monkeypatch.setattr(pipeline, "_load_content_builder", lambda: fake_content_builder)


def test_real_page_index_builder_imports_after_migration():
    page_index = pipeline._load_page_index_builder()

    assert callable(page_index)


def test_migrated_page_index_config_loader_has_defaults():
    from utils import ConfigLoader

    loaded = ConfigLoader().load()

    assert loaded.toc_check_page_num > 0
    assert loaded.max_page_num_each_node > 0


def test_process_document_builds_minimal_reading_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _install_fake_ingest_builders(monkeypatch, total_pages=3)
    pdf = tmp_path / "raw" / "demo.pdf"
    _write_dummy_pdf(pdf)

    result = pipeline.process_document(str(pdf), materialize_summaries=False)

    assert result.doc_name == "demo.pdf"
    assert result.total_pages == 3
    assert result.index_built is True
    assert result.structure_built is True
    assert result.content_built is True
    assert is_document_processed("demo.pdf") is True
    assert "error" not in get_doc_config("demo.pdf")


def test_process_document_materializes_specindex_page_spans_and_images(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _install_fake_ingest_builders(monkeypatch, total_pages=1)
    pdf = tmp_path / "raw" / "demo.pdf"
    _write_text_pdf(pdf)

    result = pipeline.process_document(str(pdf), force=True, materialize_summaries=False)

    doc_root = tmp_path / "processed_specs" / "local" / result.doc_stem
    text_payload = json.loads((doc_root / "pages" / "page_001" / "text.json").read_text(encoding="utf-8"))
    assert (doc_root / "pages" / "page_001" / "page.png").exists()
    assert (doc_root / "assets" / "assets_manifest.jsonl").exists()
    assert text_payload["doc_id"] == result.doc_stem
    assert text_payload["page"] == 1
    assert text_payload["spans"][0]["span_id"] == "p001_s0001"
    assert "Demo Packet Version" in text_payload["spans"][0]["text"]
    assert len(text_payload["spans"][0]["bbox"]) == 4

    from src.tools.page_content import get_page_content

    page = get_page_content("demo.pdf", "1")["content"][0]
    assert page["metadata"]["source"] == "processed_specs"
    assert page["text_spans"][0]["span_id"] == "p001_s0001"


def test_process_document_materializes_table_and_figure_assets(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _install_fake_ingest_builders(monkeypatch, total_pages=1)
    pdf = tmp_path / "raw" / "demo_assets.pdf"
    _write_asset_pdf(pdf)

    result = pipeline.process_document(str(pdf), force=True, materialize_summaries=False)

    doc_root = tmp_path / "processed_specs" / "local" / result.doc_stem
    manifest_lines = (doc_root / "assets" / "assets_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    manifest = [json.loads(line) for line in manifest_lines if line.strip()]
    assert {item["type"] for item in manifest} == {"table", "figure"}

    table_asset = next(item for item in manifest if item["type"] == "table")
    figure_asset = next(item for item in manifest if item["type"] == "figure")
    assert table_asset["pages"] == [1]
    assert figure_asset["pages"] == [1]
    assert table_asset["caption"] == "Table 1 Demo Packet Format"
    assert figure_asset["caption"] == "Figure 1 Demo State"

    table_root = doc_root / "tables" / table_asset["asset_id"]
    table_meta = json.loads((table_root / "table_meta.json").read_text(encoding="utf-8"))
    assert table_meta["caption"] == "Table 1 Demo Packet Format"
    cells = [
        json.loads(line)
        for line in (table_root / "cells.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert (table_root / "crop.png").exists()
    assert any(cell["text"] == "Version" and len(cell["bbox"]) == 4 for cell in cells)
    assert any(cell["text"] == "3 bits" for cell in cells)

    figure_root = doc_root / "figures" / figure_asset["asset_id"]
    assert (figure_root / "crop.png").exists()
    figure_meta = json.loads((figure_root / "figure_meta.json").read_text(encoding="utf-8"))
    assert figure_meta["bbox"]

    page_text = json.loads((doc_root / "pages" / "page_001" / "text.json").read_text(encoding="utf-8"))
    assert table_asset["asset_id"] in page_text["asset_ids"]
    assert figure_asset["asset_id"] in page_text["asset_ids"]

    from src.tools.specindex_assets import get_image, get_table, list_assets

    listed = list_assets(result.doc_stem, page_range="1")
    assert listed["asset_count"] == 2
    assert get_table(table_asset["asset_id"], doc_id=result.doc_stem)["table"]["cell_count"] >= 4
    assert get_image(figure_asset["asset_id"], doc_id=result.doc_stem)["image"]["crop_path"].endswith("crop.png")


def test_process_document_stitches_adjacent_table_fragments_into_logical_table(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _install_fake_ingest_builders(monkeypatch, total_pages=2)
    pdf = tmp_path / "raw" / "demo_continued.pdf"
    _write_two_page_continuation_table_pdf(pdf)

    result = pipeline.process_document(str(pdf), force=True, materialize_summaries=False)

    from src.tools.specindex_assets import get_table, list_assets

    listed = list_assets(result.doc_stem, page_range="1-2", type="table")
    assert listed["asset_count"] == 1
    logical_asset = listed["assets"][0]
    assert logical_asset["pages"] == [1, 2]
    assert logical_asset["fragment_ids"] == ["table_0001", "table_0002"]

    table = get_table(logical_asset["asset_id"], doc_id=result.doc_stem)["table"]
    assert table["meta"]["logical_table"] is True
    assert table["meta"]["continuation"] == {
        "type": "adjacent_same_header",
        "header_source_fragment": "table_0001",
    }
    assert table["cell_count"] >= 6
    assert any(cell["text"] == "Version" and cell["page"] == 1 for cell in table["cells"])
    assert any(cell["text"] == "Payload" and cell["page"] == 2 for cell in table["cells"])
    assert table["meta"]["pages"] == [1, 2]


def test_process_document_builds_chunks_after_asset_aware_summaries(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    events: list[str] = []
    page_index_kwargs: list[dict] = []

    def fake_page_index(pdf_path: str, **kwargs):
        events.append("index")
        page_index_kwargs.append(kwargs)
        return {
            "doc_name": Path(pdf_path).name,
            "structure": [
                {
                    "node_id": "0001",
                    "title": "Test Section",
                    "start_index": 1,
                    "end_index": 1,
                }
            ],
        }

    def fake_content_builder(pdf_path: str, output_dir: str, chunk_size: int = 20):
        events.append("content")
        json_dir = Path(output_dir) / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        out = json_dir / "content_1_1.json"
        out.write_text(
            json.dumps(
                {
                    "doc_name": Path(pdf_path).name,
                    "start_page": 1,
                    "end_page": 1,
                    "pages": [{"page_num": 1, "text": "page 1", "tables": [], "images": []}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return [out]

    def fake_assets(
        *,
        project_root: Path,
        source_pdf: Path,
        doc_stem: str,
        content_dir: Path,
        progress_callback,
    ):
        events.append("assets")
        assets_root = project_root / "processed_specs" / "local" / doc_stem / "assets"
        assets_root.mkdir(parents=True, exist_ok=True)
        (assets_root / "assets_manifest.jsonl").write_text("", encoding="utf-8")
        return assets_root.parent

    def fake_summary_stage(
        *,
        doc_name: str,
        page_index_json: Path,
        content_dir: Path,
        doc_root: Path | None,
        model: str | None,
        include_doc_description: bool,
        progress_callback,
    ):
        events.append("summary")
        payload = json.loads(page_index_json.read_text(encoding="utf-8"))
        payload["structure"][0]["summary"] = "asset-aware navigation index"
        page_index_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return True

    def fake_load_root(page_index_json: str):
        payload = json.loads(Path(page_index_json).read_text(encoding="utf-8"))
        return payload, str(payload.get("doc_name", "unknown.pdf"))

    def fake_chunk(root_node, doc_name: str, max_limit: int):
        events.append("chunk")
        return [{"success": True, "doc_name": doc_name, "structure": root_node["structure"]}]

    def fake_save_parts(parts, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "part_0001.json").write_text(
            json.dumps(parts[0], ensure_ascii=False),
            encoding="utf-8",
        )
        (output_dir / "manifest.json").write_text(
            json.dumps({"total_parts": 1, "files": ["part_0001.json"]}),
            encoding="utf-8",
        )

    monkeypatch.setattr(pipeline, "_load_page_index_builder", lambda: fake_page_index)
    monkeypatch.setattr(pipeline, "_load_content_builder", lambda: fake_content_builder)
    monkeypatch.setattr(pipeline, "_materialize_specindex_page_assets", fake_assets)
    monkeypatch.setattr(pipeline, "_run_summary_materialization_stage", fake_summary_stage)
    monkeypatch.setattr(
        pipeline,
        "_load_structure_helpers",
        lambda: (fake_load_root, fake_chunk, fake_save_parts),
    )
    pdf = tmp_path / "raw" / "demo_summary_order.pdf"
    _write_dummy_pdf(pdf)

    result = pipeline.process_document(str(pdf), force=True, materialize_summaries=True)

    assert result.summary_built is True
    assert page_index_kwargs[0]["if_add_node_summary"] == "no"
    assert events == ["index", "content", "assets", "summary", "chunk"]
    part = json.loads((tmp_path / "data" / "out" / "chunk" / "demo_summary_order" / "part_0001.json").read_text())
    assert part["structure"][0]["summary"] == "asset-aware navigation index"


def test_materialized_summaries_include_compact_asset_context(tmp_path: Path, monkeypatch):
    captured_prompts: list[str] = []

    async def fake_chatgpt_api_async(model, prompt, **_kwargs):
        captured_prompts.append(prompt)
        return "navigation summary"

    monkeypatch.setenv("PROTOCOL_TWIN_SUMMARY_CACHE_DIR", str(tmp_path / "summary-cache"))
    monkeypatch.setattr("utils.ChatGPT_API_async", fake_chatgpt_api_async)

    page_index_json = tmp_path / "page_index.json"
    page_index_json.write_text(
        json.dumps(
            {
                "doc_name": "demo.pdf",
                "structure": [
                    {
                        "node_id": "0001",
                        "title": "Test Section",
                        "start_index": 1,
                        "end_index": 1,
                        "text": "This section references a packet table and a state figure.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    content_dir = tmp_path / "content" / "json"
    content_dir.mkdir(parents=True)

    doc_root = tmp_path / "processed_specs" / "local" / "demo"
    assets_root = doc_root / "assets"
    assets_root.mkdir(parents=True)
    (assets_root / "assets_manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "asset_id": "table_0001",
                        "type": "table",
                        "caption": "Table 1 Packet Header",
                        "pages": [1],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "asset_id": "figure_0001",
                        "type": "figure",
                        "caption": "Figure 1 State Flow",
                        "pages": [1],
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    table_root = doc_root / "tables" / "table_0001"
    table_root.mkdir(parents=True)
    (table_root / "table.json").write_text(
        json.dumps(
            {
                "rows": [
                    ["Field", "Width", "Description"],
                    ["Version", "3 bits", "Protocol version"],
                    ["SHOULD_NOT_APPEAR", "999 bits", "third row should stay out of prompt"],
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (table_root / "cells.jsonl").write_text(
        "\n".join(json.dumps({"cell_id": f"c{i}", "text": str(i)}) for i in range(9)) + "\n",
        encoding="utf-8",
    )
    figure_root = doc_root / "figures" / "figure_0001"
    figure_root.mkdir(parents=True)
    (figure_root / "vision_summary.json").write_text(
        json.dumps({"summary": ""}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = pipeline._materialize_document_summaries(
        page_index_json=page_index_json,
        content_dir=content_dir,
        doc_root=doc_root,
        model="test-model",
    )

    assert result["summary_count"] == 1
    assert captured_prompts
    prompt = captured_prompts[0]
    assert "Table 1 Packet Header" in prompt
    assert "Figure 1 State Flow" in prompt
    assert "Field | Width | Description" in prompt
    assert "Version | 3 bits | Protocol version" in prompt
    assert "SHOULD_NOT_APPEAR" not in prompt

    payload = json.loads(page_index_json.read_text(encoding="utf-8"))
    node = payload["structure"][0]
    assert node["summary"] == "navigation summary"
    assert "_summary_assets" not in node


def test_materialized_summaries_do_not_reexpand_flat_target_nodes(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    async def fake_chatgpt_api_async(model, prompt, **_kwargs):
        calls.append(prompt)
        return f"summary {len(calls)}"

    monkeypatch.setenv("PROTOCOL_TWIN_SUMMARY_CACHE_DIR", "disabled")
    monkeypatch.setattr("utils.ChatGPT_API_async", fake_chatgpt_api_async)

    page_index_json = tmp_path / "page_index.json"
    page_index_json.write_text(
        json.dumps(
            {
                "doc_name": "demo.pdf",
                "structure": [
                    {
                        "node_id": "parent",
                        "title": "Parent Section",
                        "start_index": 1,
                        "end_index": 1,
                        "text": "Parent text.",
                        "nodes": [
                            {
                                "node_id": "child",
                                "title": "Child Section",
                                "start_index": 1,
                                "end_index": 1,
                                "text": "Child text.",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    content_dir = tmp_path / "content" / "json"
    content_dir.mkdir(parents=True)

    result = pipeline._materialize_document_summaries(
        page_index_json=page_index_json,
        content_dir=content_dir,
        model="test-model",
    )

    assert result["summary_count"] == 2
    assert len(calls) == 2
    payload = json.loads(page_index_json.read_text(encoding="utf-8"))
    parent = payload["structure"][0]
    child = parent["nodes"][0]
    assert parent["summary"] == "summary 1"
    assert child["summary"] == "summary 2"


def test_agentic_rag_loop_runs_without_old_ir_models(monkeypatch):
    class FakeAdapter:
        def __init__(self, provider: str, model: str):
            self.calls = 0

        async def chat_with_tools(self, _messages, _tools):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    has_tool_calls=True,
                    tool_calls=[
                        ToolCall(
                            name="get_page_content",
                            arguments={"doc_name": "demo.pdf", "pages": "1"},
                            id="tc1",
                        )
                    ],
                    usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
                    raw_message={
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "tc1",
                                "type": "function",
                                "function": {
                                    "name": "get_page_content",
                                    "arguments": "{\"doc_name\":\"demo.pdf\",\"pages\":\"1\"}",
                                },
                            }
                        ],
                    },
                )
            return LLMResponse(
                has_tool_calls=False,
                text="Answer [demo.pdf p.1]",
                usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
                raw_message={"role": "assistant", "content": "Answer [demo.pdf p.1]"},
            )

        def make_tool_result_message(self, tool_call_id: str, result: dict) -> dict:
            return {"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(result)}

    monkeypatch.setattr(loop, "LLMAdapter", FakeAdapter)
    monkeypatch.setattr(loop, "load_system_prompt", lambda *_args, **_kwargs: "system")
    monkeypatch.setattr(loop, "get_tool_schemas", lambda: [])
    monkeypatch.setattr(
        loop,
        "execute_tool",
        lambda _name, _arguments: {"content": [{"page": 1, "text": "ok", "tables": [], "images": []}]},
    )
    monkeypatch.setattr(loop, "_save_session", lambda *_args, **_kwargs: None)

    response = asyncio.run(loop.agentic_rag(query="q", doc_name="demo.pdf", max_turns=3))

    assert response.answer == "Answer [demo.pdf p.1]"
    assert response.pages_retrieved == [1]
    assert response.trace[0].tool == "get_page_content"


def test_web_health_route():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
