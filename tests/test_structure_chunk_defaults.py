from __future__ import annotations

import inspect
from pathlib import Path


def test_structure_chunk_default_limit_is_70k():
    from src.ingest import pipeline
    from src.web.app import ProcessPathRequest, QARequest

    assert inspect.signature(pipeline.process_document).parameters["structure_max_limit"].default == 70_000
    assert inspect.signature(pipeline.ensure_document_ready).parameters["structure_max_limit"].default == 70_000
    assert ProcessPathRequest(pdf_path="demo.pdf").structure_max_limit == 70_000
    assert QARequest(query="demo").structure_max_limit == 70_000

    html = Path("src/web/static/index.html").read_text(encoding="utf-8")
    assert "PROCESS_SETTINGS_STORAGE_KEY = 'kiro.process.settings.v2'" in html
    assert "LEGACY_PROCESS_SETTINGS_STORAGE_KEYS = ['kiro.process.settings.v1']" in html
    assert "structure_chunk_max_limit: 70000" in html
