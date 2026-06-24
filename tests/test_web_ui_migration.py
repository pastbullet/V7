from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% web ui smoke\n")


def _write_processed_doc(root: Path, doc_name: str = "demo.pdf") -> None:
    chunk_dir = root / "data" / "out" / "chunk" / "demo"
    content_dir = root / "data" / "out" / "content" / "demo" / "json"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / "manifest.json").write_text(json.dumps({"total_parts": 1}), encoding="utf-8")
    (chunk_dir / "part_0001.json").write_text(json.dumps({"structure": []}), encoding="utf-8")
    (chunk_dir / "page_index.json").write_text(json.dumps({"structure": []}), encoding="utf-8")
    (content_dir / "content_1_1.json").write_text(
        json.dumps({"pages": [{"page_num": 1, "text": "demo"}]}),
        encoding="utf-8",
    )
    _write_pdf(root / "data" / "raw" / doc_name)
    (root / "data" / "out" / "doc_registry.runtime.json").write_text(
        json.dumps(
            {
                doc_name: {
                    "chunks_dir": str(chunk_dir.relative_to(root)),
                    "content_dir": str(content_dir.relative_to(root)),
                    "total_pages": 1,
                    "pdf_path": f"data/raw/{doc_name}",
                }
            }
        ),
        encoding="utf-8",
    )


def test_root_serves_migrated_m1_html_ui():
    from src.web.app import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="app-root"' in response.text
    assert "/api/qa/stream" in response.text
    assert "/api/conversations" in response.text


def test_docs_endpoint_keeps_ui_compatible_shape(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_processed_doc(tmp_path)

    from src.web.app import app

    client = TestClient(app)
    response = client.get("/api/docs")

    assert response.status_code == 200
    docs = response.json()["docs"]
    demo = next(doc for doc in docs if doc.get("doc_name") == "demo.pdf")
    assert demo["processed"] is True
    assert demo["name"] == "demo.pdf"


def test_conversation_routes_group_session_logs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions = tmp_path / "data" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "20260624_090000.json").write_text(
        json.dumps(
            {
                "timestamp": "20260624_090000",
                "doc_name": "demo.pdf",
                "query": "hello",
                "answer": "world",
                "answer_clean": "world",
                "trace": [],
                "citations": [],
                "pages_retrieved": [1],
                "total_turns": 1,
                "context_session_id": "sess_demo",
            }
        ),
        encoding="utf-8",
    )

    from src.web import app as web_app

    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(web_app, "SESSION_LOG_DIR", sessions)
    client = TestClient(web_app.app)

    listed = client.get("/api/conversations")
    assert listed.status_code == 200
    conversations = listed.json()["conversations"]
    assert conversations[0]["id"] == "sess_demo"

    detail = client.get("/api/conversations/sess_demo")
    assert detail.status_code == 200
    assert detail.json()["entries"][0]["query"] == "hello"


def test_pdf_route_serves_registered_pdf(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_processed_doc(tmp_path)

    from src.web import app as web_app

    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    client = TestClient(web_app.app)
    response = client.get("/api/pdf/demo.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
