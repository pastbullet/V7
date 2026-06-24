from __future__ import annotations

from structure_chunker import Node, chunk_document_structure, save_parts_to_folder


def _find_node(nodes, node_id):
    for node in nodes:
        if node.get("node_id") == node_id:
            return node
        found = _find_node(node.get("children", []), node_id)
        if found is not None:
            return found
    return None


def test_chunker_emits_subtree_page_range_for_parent_sections():
    root = Node(
        node_id="root",
        title="Root",
        start_index=1,
        end_index=1,
        children=[
            Node(
                node_id="parent",
                title="Parent",
                start_index=10,
                end_index=10,
                children=[
                    Node(node_id="child-a", title="Child A", start_index=11, end_index=12),
                    Node(
                        node_id="child-b",
                        title="Child B",
                        start_index=14,
                        end_index=14,
                        children=[
                            Node(node_id="grandchild", title="Grandchild", start_index=15, end_index=16)
                        ],
                    ),
                ],
            )
        ],
    )

    parts = chunk_document_structure(root, doc_name="demo.pdf", max_limit=10_000)
    parent = _find_node(parts[0]["structure"], "parent")
    child_b = _find_node(parts[0]["structure"], "child-b")

    assert parent["start_index"] == 10
    assert parent["end_index"] == 10
    assert parent["subtree_start_index"] == 10
    assert parent["subtree_end_index"] == 16
    assert child_b["subtree_start_index"] == 14
    assert child_b["subtree_end_index"] == 16


def test_skeleton_ancestor_keeps_summary_when_structure_is_chunked():
    root = Node(
        node_id="root",
        title="Root",
        children=[
            Node(
                node_id="parent",
                title="Parent",
                summary="Parent navigation summary.",
                children=[
                    Node(node_id=f"child-{index}", title=f"Child {index}", summary="x" * 80)
                    for index in range(4)
                ],
            )
        ],
    )

    parts = chunk_document_structure(root, doc_name="demo.pdf", max_limit=240)

    skeletons = [
        node
        for part in parts[1:]
        for node in part["structure"]
        if node.get("node_id") == "parent" and node.get("is_skeleton") is True
    ]

    assert skeletons
    assert all(node.get("summary") == "Parent navigation summary." for node in skeletons)


def test_skeleton_ancestor_keeps_subtree_range_when_structure_is_chunked():
    root = Node(
        node_id="root",
        title="Root",
        children=[
            Node(
                node_id="parent",
                title="Parent",
                summary="Parent navigation summary.",
                start_index=10,
                end_index=10,
                children=[
                    Node(node_id=f"child-{index}", title=f"Child {index}", summary="x" * 80, start_index=11 + index, end_index=11 + index)
                    for index in range(4)
                ],
            )
        ],
    )

    parts = chunk_document_structure(root, doc_name="demo.pdf", max_limit=260)
    skeletons = [
        node
        for part in parts[1:]
        for node in part["structure"]
        if node.get("node_id") == "parent" and node.get("is_skeleton") is True
    ]

    assert skeletons
    assert all(node.get("subtree_start_index") == 10 for node in skeletons)
    assert all(node.get("subtree_end_index") == 14 for node in skeletons)


def test_save_parts_to_folder_removes_stale_part_files(tmp_path):
    output_dir = tmp_path / "chunks"
    output_dir.mkdir()
    stale = output_dir / "part_0003.json"
    stale.write_text('{"stale": true}', encoding="utf-8")

    parts = [
        {"success": True, "doc_name": "demo.pdf", "structure": []},
        {"success": True, "doc_name": "demo.pdf", "structure": []},
    ]

    save_parts_to_folder(parts, output_dir)

    assert (output_dir / "part_0001.json").exists()
    assert (output_dir / "part_0002.json").exists()
    assert not stale.exists()
