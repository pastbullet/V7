from __future__ import annotations

import json
from pathlib import Path

from src.agent.loop import TOOL_REGISTRY, load_system_prompt
from src.tools.schemas import get_tool_schemas


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_specindex_fixture(root: Path) -> None:
    doc_root = root / "processed_specs" / "demo" / "demo_doc"

    _write_json(
        doc_root / "pages" / "page_001" / "text.json",
        {
            "doc_id": "demo_doc",
            "page": 1,
            "spans": [
                {
                    "span_id": "p001_s001",
                    "text": "The Demo Packet carries a Version field.",
                    "bbox": [10, 20, 200, 40],
                    "section_id": "sec_1",
                }
            ],
            "asset_ids": ["table_0001", "figure_0001"],
        },
    )
    _write_text(doc_root / "pages" / "page_001" / "page.png", "fake png placeholder")

    _write_text(
        doc_root / "assets" / "assets_manifest.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "asset_id": "table_0001",
                        "type": "table",
                        "caption": "Demo Packet Format",
                        "section_id": "sec_1",
                        "pages": [1],
                        "path": "tables/table_0001/table_meta.json",
                    }
                ),
                json.dumps(
                    {
                        "asset_id": "figure_0001",
                        "type": "figure",
                        "caption": "Demo State Machine",
                        "section_id": "sec_1",
                        "pages": [1],
                        "path": "figures/figure_0001/figure_meta.json",
                    }
                ),
            ]
        )
        + "\n",
    )

    _write_json(
        doc_root / "tables" / "table_0001" / "table_meta.json",
        {
            "asset_id": "table_0001",
            "type": "table",
            "caption": "Demo Packet Format",
            "section_id": "sec_1",
            "pages": [1],
            "bbox": [10, 60, 300, 160],
            "source_crop": "crop.png",
            "context_file": "context.md",
        },
    )
    _write_text(
        doc_root / "tables" / "table_0001" / "table.md",
        "| Field | Width |\n| --- | --- |\n| Version | 3 bits |\n",
    )
    _write_json(
        doc_root / "tables" / "table_0001" / "table.json",
        {"rows": [{"Field": "Version", "Width": "3 bits"}]},
    )
    _write_text(
        doc_root / "tables" / "table_0001" / "cells.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "cell_id": "r1c1",
                        "row": 1,
                        "col": 1,
                        "text": "Version",
                        "page": 1,
                        "bbox": [20, 80, 80, 100],
                    }
                ),
                json.dumps(
                    {
                        "cell_id": "r1c2",
                        "row": 1,
                        "col": 2,
                        "text": "3 bits",
                        "page": 1,
                        "bbox": [90, 80, 130, 100],
                    }
                ),
            ]
        )
        + "\n",
    )
    _write_text(doc_root / "tables" / "table_0001" / "context.md", "Surrounding table context.")
    _write_text(doc_root / "tables" / "table_0001" / "crop.png", "fake table crop")

    _write_json(
        doc_root / "figures" / "figure_0001" / "figure_meta.json",
        {
            "asset_id": "figure_0001",
            "type": "figure",
            "image_type": "state_machine_diagram",
            "caption": "Demo State Machine",
            "section_id": "sec_1",
            "pages": [1],
            "bbox": [10, 180, 300, 360],
            "source_crop": "crop.png",
            "context_file": "context.md",
            "vision_summary_file": "vision_summary.json",
        },
    )
    _write_text(doc_root / "figures" / "figure_0001" / "crop.png", "fake figure crop")
    _write_text(doc_root / "figures" / "figure_0001" / "context.md", "Figure surrounding context.")
    _write_json(
        doc_root / "figures" / "figure_0001" / "vision_summary.json",
        {"derived": True, "summary": "Derived summary, not evidence."},
    )


def test_agent_loop_exposes_specindex_tools_only():
    assert set(TOOL_REGISTRY) == {
        "get_document_structure",
        "get_page_content",
        "list_assets",
        "get_table",
        "get_image",
        "verify_evidence",
    }

    schema_names = {
        schema["function"]["name"]
        for schema in get_tool_schemas()
    }
    assert schema_names == set(TOOL_REGISTRY)
    assert "search_nodes" not in schema_names
    assert "get_prev_node" not in schema_names
    assert "get_next_node" not in schema_names


def test_list_assets_schema_exposes_caption_query():
    schema = next(schema for schema in get_tool_schemas() if schema["function"]["name"] == "list_assets")

    assert "caption_query" in schema["function"]["parameters"]["properties"]


def test_get_page_content_page_parser_accepts_mixed_comma_ranges():
    from src.tools.page_content import parse_pages

    assert parse_pages("36,166-170,179,203") == [36, 166, 167, 168, 169, 170, 179, 203]


def test_verify_evidence_schema_documents_canonical_ref_shapes():
    schema = next(schema for schema in get_tool_schemas() if schema["function"]["name"] == "verify_evidence")
    refs = schema["function"]["parameters"]["properties"]["evidence_refs"]

    variants = refs["items"]["oneOf"]
    variant_by_type = {
        variant["properties"]["type"]["enum"][0]: variant
        for variant in variants
    }

    assert set(variant_by_type) == {"text_span", "table_cell", "figure_crop", "figure_region"}
    assert variant_by_type["text_span"]["required"] == ["type", "span_id"]
    assert variant_by_type["table_cell"]["required"] == ["type", "asset_id", "cell_id"]
    assert variant_by_type["figure_crop"]["required"] == ["type", "asset_id"]


def test_specindex_prompt_requires_structure_page_asset_evidence_flow():
    prompt = load_system_prompt("specindex_system.txt")

    assert "get_document_structure" in prompt
    assert "get_page_content" in prompt
    assert "get_table" in prompt
    assert "get_image" in prompt
    assert "span/cell/crop" in prompt
    assert '<cite doc="DOC_NAME" page="N"/>' in prompt
    assert "vision_summary" in prompt
    assert "search_nodes" not in prompt


def test_unit_discovery_prompt_requires_following_referenced_payload_assets():
    prompt = load_system_prompt("unit_discovery_system.txt")

    assert "referenced" in prompt
    assert "payload" in prompt
    assert "message structure" in prompt
    assert "caption_query" in prompt
    assert "list_assets" in prompt
    assert "get_table" in prompt
    assert "table-derived unit" in prompt
    assert "related table asset" in prompt
    assert "table_cell" in prompt
    assert "related_assets" in prompt
    assert "unresolved" in prompt
    assert "search_nodes" not in prompt


def test_reading_claim_prompt_requires_caption_query_for_referenced_assets():
    prompt = load_system_prompt("reading_claim_system.txt")

    assert "caption_query" in prompt
    assert "table_cell" in prompt
    assert "get_table" in prompt
    assert "vision_summary" in prompt
    assert "search_nodes" not in prompt


def test_pageindex_reading_prompt_documents_verify_evidence_ref_shape():
    prompt = load_system_prompt("pageindex_reading.txt")

    assert "verify_evidence" in prompt
    assert '{"type": "text_span", "span_id": "...", "quote": "..."}' in prompt
    assert '{"type": "table_cell", "asset_id": "...", "cell_id": "...", "quote": "..."}' in prompt


def test_pageindex_reading_prompt_explains_subtree_cross_refs_and_prior_boundary():
    prompt = load_system_prompt("pageindex_reading.txt")

    assert "subtree_start_index/subtree_end_index" in prompt
    assert "start_index/end_index is the node's own text range" in prompt
    assert "Never request more than 10 pages" in prompt
    assert "caption_query" in prompt
    assert "see clause/section" in prompt
    assert "Prior/background knowledge" in prompt
    assert "Document facts require retrieved page evidence" in prompt
    assert "You may reorganize retrieved clauses" in prompt


def test_document_structure_next_steps_explain_own_vs_subtree_ranges(tmp_path: Path, monkeypatch):
    chunks_dir = tmp_path / "chunks"
    content_dir = tmp_path / "content"
    chunks_dir.mkdir()
    content_dir.mkdir()
    _write_json(chunks_dir / "manifest.json", {"total_parts": 1})
    _write_json(
        chunks_dir / "part_0001.json",
        {
            "structure": [
                {
                    "node_id": "parent",
                    "title": "Parent",
                    "start_index": 10,
                    "end_index": 10,
                    "subtree_start_index": 10,
                    "subtree_end_index": 12,
                    "children": [],
                }
            ]
        },
    )

    from src.tools import document_structure

    monkeypatch.setattr(
        document_structure,
        "get_doc_config",
        lambda doc_name: {
            "chunks_dir": str(chunks_dir),
            "content_dir": str(content_dir),
            "total_pages": 12,
        },
    )

    result = document_structure.get_document_structure("demo.pdf", part=1)

    assert result["structure"][0]["subtree_end_index"] == 12
    assert "start_index/end_index describe the node's own text range" in result["next_steps"]
    assert "subtree_start_index/subtree_end_index describe the full descendant section range" in result["next_steps"]
    assert "Do not read a large subtree in one call" in result["next_steps"]


def test_specindex_asset_tools_read_processed_specs_layout(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_specindex_fixture(tmp_path)

    from src.tools.specindex_assets import get_image, get_table, list_assets

    listed = list_assets(doc_id="demo_doc", page_range="1", type="table")
    assert listed["asset_count"] == 1
    assert listed["assets"][0]["asset_id"] == "table_0001"

    caption_match = list_assets(doc_id="demo_doc", type="table", caption_query="Demo Packet")
    assert caption_match["asset_count"] == 1
    assert caption_match["assets"][0]["asset_id"] == "table_0001"

    table = get_table(table_id="table_0001", doc_id="demo_doc", view="full")
    assert table["table"]["meta"]["caption"] == "Demo Packet Format"
    assert table["table"]["markdown"].startswith("| Field | Width |")
    assert table["table"]["cells"][1]["cell_id"] == "r1c2"
    assert table["table"]["cell_count"] == 2

    image = get_image(image_id="figure_0001", doc_id="demo_doc", view="full")
    assert image["image"]["meta"]["caption"] == "Demo State Machine"
    assert image["image"]["vision_summary"]["derived"] is True
    assert image["image"]["crop_path"].endswith("figures/figure_0001/crop.png")


def test_specindex_asset_tools_accept_pdf_doc_name_alias(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_specindex_fixture(tmp_path)

    from src.tools.specindex_assets import get_image, get_table, list_assets, verify_evidence

    listed = list_assets(doc_id="demo_doc.pdf", page_range="1")
    assert listed["asset_count"] == 2

    table = get_table(table_id="table_0001", doc_id="demo_doc.pdf")
    assert table["table"]["doc_id"] == "demo_doc"

    image = get_image(image_id="figure_0001", doc_id="demo_doc.pdf")
    assert image["image"]["doc_id"] == "demo_doc"

    verified = verify_evidence(
        doc_id="demo_doc.pdf",
        claim="Version is present.",
        evidence_refs=[{"type": "text_span", "span_id": "p001_s001", "quote": "Version"}],
    )
    assert verified["status"] == "accepted"


def test_get_page_content_returns_specindex_spans_assets_and_page_image(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_specindex_fixture(tmp_path)

    from src.tools.page_content import get_page_content

    result = get_page_content(doc_name="demo_doc", pages="1")

    assert "error" not in result
    page = result["content"][0]
    assert page["page"] == 1
    assert page["text_spans"][0]["span_id"] == "p001_s001"
    assert page["text_spans"][0]["bbox"] == [10, 20, 200, 40]
    assert page["asset_refs"] == ["table_0001", "figure_0001"]
    assert page["page_image_path"].endswith("pages/page_001/page.png")
    assert page["metadata"]["source"] == "processed_specs"


def test_verify_evidence_structurally_checks_span_cell_and_crop(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_specindex_fixture(tmp_path)

    from src.tools.specindex_assets import verify_evidence

    result = verify_evidence(
        doc_id="demo_doc",
        claim="The Version field is 3 bits wide.",
        evidence_refs=[
            {"type": "text_span", "span_id": "p001_s001", "quote": "Version field"},
            {"type": "table_cell", "asset_id": "table_0001", "cell_id": "r1c2", "quote": "3 bits"},
            {"type": "figure_crop", "asset_id": "figure_0001"},
        ],
    )

    assert result["status"] == "accepted"
    assert result["invalid_count"] == 0
    assert len(result["checked_refs"]) == 3

    rejected = verify_evidence(
        doc_id="demo_doc",
        claim="Derived summaries are not raw evidence.",
        evidence_refs=[
            {"type": "vision_summary", "asset_id": "figure_0001"},
            {"type": "table_cell", "asset_id": "table_0001", "cell_id": "missing"},
        ],
    )

    assert rejected["status"] == "invalid"
    assert rejected["invalid_count"] == 2
    assert "not an allowed raw evidence type" in rejected["invalid_refs"][0]["reason"]


def test_verify_evidence_accepts_wrapped_ref_shape_from_tool_call(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _build_specindex_fixture(tmp_path)

    from src.tools.specindex_assets import verify_evidence

    result = verify_evidence(
        doc_id="demo_doc",
        claim="The Version field is present.",
        evidence_refs=[
            {"text_span": {"page": 1, "span_id": "p001_s001", "quote": "Version field"}},
        ],
    )

    assert result["status"] == "accepted"
    assert result["checked_refs"][0]["ref"] == {
        "type": "text_span",
        "page": 1,
        "span_id": "p001_s001",
        "quote": "Version field",
    }
