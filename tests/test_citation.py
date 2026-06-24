from __future__ import annotations

from src.agent.citation import extract_citations


def test_extract_citations_accepts_cite_tags_and_inline_page_refs():
    answer = (
        'Fact one <cite doc="demo.pdf" page="3"/>.\n'
        "Fact two evidence: `demo.pdf:4`.\n"
        "Fact three evidence: demo.pdf:5."
    )

    citations = extract_citations(answer)

    assert [(c.doc_name, c.page) for c in citations] == [
        ("demo.pdf", 3),
        ("demo.pdf", 4),
        ("demo.pdf", 5),
    ]
