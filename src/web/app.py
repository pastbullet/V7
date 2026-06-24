"""V7 Agentic RAG web service.

This is a slim web entry for the reading layer described in
``V7_REFACTOR_ARCHITECTURE.md``.  It intentionally excludes M1/V6 extraction,
audit, and IR-audit routes; V7 will add those back through new grounded
interfaces after the reading layer is stable.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agent.loop import agentic_rag
from src.ingest.pipeline import ProcessResult, ensure_document_ready, process_document
from src.tools.registry import get_doc_config, get_registered_documents, is_document_processed

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_LOG_DIR = PROJECT_ROOT / "data" / "sessions"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

ProgressEmitter = Callable[[dict[str, Any]], None]
StreamWork = Callable[[ProgressEmitter], Awaitable[dict[str, Any] | None]]


class ProcessPathRequest(BaseModel):
    pdf_path: str = Field(min_length=1)
    force: bool = False
    model: str | None = None
    toc_check_pages: int | None = None
    max_pages_per_node: int | None = None
    max_tokens_per_node: int | None = None
    if_add_node_id: str | None = "yes"
    if_add_node_summary: str | None = "yes"
    if_add_node_text: str | None = "no"
    if_add_doc_description: str | None = "no"
    structure_max_limit: int = 70000
    content_chunk_size: int = 20


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class QARequest(BaseModel):
    query: str = Field(min_length=1)
    doc_name: str | None = None
    pdf_path: str | None = None
    history: list[dict[str, str]] | None = None
    force: bool = False
    model: str | None = None
    prompt_file: str = "specindex_system.txt"
    max_turns: int = Field(default=15, ge=1, le=80)
    enable_context_reuse: bool | None = None
    context_session_id: str | None = None
    toc_check_pages: int | None = None
    max_pages_per_node: int | None = None
    max_tokens_per_node: int | None = None
    if_add_node_id: str | None = "yes"
    if_add_node_summary: str | None = "yes"
    if_add_node_text: str | None = "no"
    if_add_doc_description: str | None = "no"
    structure_max_limit: int = 70000
    content_chunk_size: int = 20


def _process_result_to_dict(result: ProcessResult) -> dict[str, Any]:
    return asdict(result)


def _rag_response_to_dict(response: Any) -> dict[str, Any]:
    return {
        "answer": response.answer,
        "answer_clean": response.answer_clean,
        "citations": [c.model_dump() for c in response.citations],
        "trace": [t.model_dump() for t in response.trace],
        "pages_retrieved": response.pages_retrieved,
        "all_pages_requested": response.all_pages_requested,
        "total_turns": response.total_turns,
        "context_session_id": response.context_session_id,
    }


def _normalize_doc_name(doc_name: str) -> str:
    name = Path(doc_name).name.strip()
    if not name:
        raise ValueError("Document name is empty")
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name


def _to_abs(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _session_path(session_id: str) -> Path:
    safe_id = Path(session_id).name
    if safe_id.endswith(".json"):
        safe_id = safe_id[:-5]
    return SESSION_LOG_DIR / f"{safe_id}.json"


def _load_session_file(session_id: str) -> dict[str, Any]:
    safe_id = Path(session_id).name.removesuffix(".json")
    path = _session_path(safe_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {safe_id}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {safe_id}") from exc


def _session_timestamp(session_id: str, payload: dict[str, Any]) -> str:
    value = payload.get("timestamp", session_id)
    return value if isinstance(value, str) and value else session_id


def _conversation_id_for_session(session_id: str, payload: dict[str, Any]) -> str:
    context_session_id = payload.get("context_session_id")
    if isinstance(context_session_id, str) and context_session_id.strip():
        return context_session_id.strip()
    return session_id


def _iter_session_records() -> list[dict[str, Any]]:
    SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for path in sorted(SESSION_LOG_DIR.glob("*.json"), reverse=True):
        payload = _load_session_file(path.stem)
        session_id = path.stem
        records.append(
            {
                "id": session_id,
                "path": path,
                "payload": payload,
                "timestamp": _session_timestamp(session_id, payload),
                "conversation_id": _conversation_id_for_session(session_id, payload),
            }
        )
    return records


def _build_conversation_summary(conversation_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda item: item["timestamp"])
    latest = ordered[-1]
    latest_payload = latest["payload"]
    title = ""
    for item in reversed(ordered):
        value = item["payload"].get("title", "")
        if isinstance(value, str) and value.strip():
            title = value.strip()
            break
    return {
        "id": conversation_id,
        "context_session_id": latest_payload.get("context_session_id"),
        "timestamp": latest["timestamp"],
        "doc_name": latest_payload.get("doc_name", ""),
        "query": latest_payload.get("query", ""),
        "title": title,
        "total_turns": latest_payload.get("total_turns", 0),
        "pages_retrieved": latest_payload.get("pages_retrieved", []),
        "entry_count": len(ordered),
        "session_ids": [item["id"] for item in ordered],
    }


def _build_conversation_entry(record: dict[str, Any]) -> dict[str, Any]:
    payload = record["payload"]
    return {
        "id": record["id"],
        "timestamp": record["timestamp"],
        "doc_name": payload.get("doc_name", ""),
        "query": payload.get("query", ""),
        "title": payload.get("title", ""),
        "answer": payload.get("answer", ""),
        "answer_clean": payload.get("answer_clean", ""),
        "citations": payload.get("citations", []),
        "trace": payload.get("trace", []),
        "pages_retrieved": payload.get("pages_retrieved", []),
        "total_turns": payload.get("total_turns", 0),
        "context_session_id": payload.get("context_session_id"),
    }


def _get_conversation_records(conversation_id: str) -> list[dict[str, Any]]:
    safe_id = Path(conversation_id).name
    records = [
        record
        for record in _iter_session_records()
        if record["conversation_id"] == safe_id
    ]
    if not records:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {safe_id}")
    return sorted(records, key=lambda item: item["timestamp"])


def _resolve_pdf_file(doc_name: str) -> Path:
    normalized = _normalize_doc_name(doc_name)
    config = get_doc_config(normalized)
    if "error" not in config:
        pdf_path = config.get("pdf_path")
        if isinstance(pdf_path, str) and pdf_path:
            candidate = _to_abs(pdf_path)
            if candidate.exists() and candidate.is_file():
                return candidate
    raw_candidate = PROJECT_ROOT / "data" / "raw" / normalized
    if raw_candidate.exists() and raw_candidate.is_file():
        return raw_candidate.resolve()
    raise HTTPException(status_code=404, detail=f"PDF not found for {normalized}")


def _sse_pack(payload: dict[str, Any]) -> str:
    return f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_events(work: StreamWork) -> Any:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    finished = False

    def emit(payload: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, payload)

    async def runner() -> None:
        nonlocal finished
        try:
            result = await work(emit)
            emit({"type": "done", "result": result or {}})
        except Exception as exc:
            logger.exception("Stream worker failed")
            emit({"type": "error", "message": str(exc)})
            emit({"type": "done", "ok": False})
        finally:
            finished = True

    task = asyncio.create_task(runner())
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2.5)
            except asyncio.TimeoutError:
                if finished and queue.empty():
                    break
                yield _sse_pack({"type": "heartbeat", "ts": datetime.now().isoformat(timespec="seconds")})
                continue
            yield _sse_pack(event)
            if event.get("type") == "done":
                break
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="V7 Agentic RAG", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/docs")
def list_docs() -> dict[str, Any]:
    docs = []
    for name, config in sorted(get_registered_documents().items()):
        docs.append(
            {
                "doc_name": name,
                "name": name,
                "processed": is_document_processed(name),
                **dict(config),
            }
        )
    return {"docs": docs}


@app.post("/api/process/path")
async def process_path(req: ProcessPathRequest) -> dict[str, Any]:
    result = await asyncio.to_thread(
        process_document,
        pdf_path=req.pdf_path,
        force=req.force,
        model=req.model,
        toc_check_pages=req.toc_check_pages,
        max_pages_per_node=req.max_pages_per_node,
        max_tokens_per_node=req.max_tokens_per_node,
        if_add_node_id=req.if_add_node_id,
        if_add_node_summary=req.if_add_node_summary,
        if_add_node_text=req.if_add_node_text,
        if_add_doc_description=req.if_add_doc_description,
        preclassify_nodes=False,
        structure_max_limit=req.structure_max_limit,
        content_chunk_size=req.content_chunk_size,
    )
    return {"ok": True, "result": _process_result_to_dict(result)}


@app.post("/api/process/upload")
async def process_upload(
    file: UploadFile = File(...),
    force: bool = Form(False),
    model: str | None = Form(None),
    process_options_json: str | None = Form(None),
) -> dict[str, Any]:
    filename = Path(file.filename or "uploaded.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / filename
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = UPLOAD_DIR / f"{target.stem}_{stamp}{target.suffix}"
    target.write_bytes(await file.read())
    options: dict[str, Any] = {}
    if process_options_json:
        try:
            raw_options = json.loads(process_options_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid process_options_json") from exc
        if isinstance(raw_options, dict):
            allowed = {
                "toc_check_pages",
                "max_pages_per_node",
                "max_tokens_per_node",
                "if_add_node_id",
                "if_add_node_summary",
                "if_add_node_text",
                "if_add_doc_description",
                "structure_max_limit",
                "content_chunk_size",
            }
            options = {key: value for key, value in raw_options.items() if key in allowed and value is not None}
    result = await asyncio.to_thread(
        process_document,
        pdf_path=str(target),
        force=force,
        model=model,
        preclassify_nodes=False,
        **options,
    )
    return {"ok": True, "saved_pdf": str(target), "result": _process_result_to_dict(result)}


@app.post("/api/qa")
async def qa(req: QARequest) -> dict[str, Any]:
    if bool(req.doc_name) == bool(req.pdf_path):
        raise HTTPException(status_code=400, detail="Provide exactly one of doc_name or pdf_path.")

    ready = await asyncio.to_thread(
        ensure_document_ready,
        doc=req.doc_name,
        pdf=req.pdf_path,
        force=req.force,
        model=req.model,
        toc_check_pages=req.toc_check_pages,
        max_pages_per_node=req.max_pages_per_node,
        max_tokens_per_node=req.max_tokens_per_node,
        if_add_node_id=req.if_add_node_id,
        if_add_node_summary=req.if_add_node_summary,
        if_add_node_text=req.if_add_node_text,
        if_add_doc_description=req.if_add_doc_description,
        structure_max_limit=req.structure_max_limit,
        content_chunk_size=req.content_chunk_size,
    )
    response = await agentic_rag(
        query=req.query,
        doc_name=ready.doc_name,
        model=req.model,
        max_turns=req.max_turns,
        prompt_file=req.prompt_file,
        history_messages=req.history,
        enable_context_reuse=req.enable_context_reuse,
        context_session_id=req.context_session_id,
    )
    return {
        "ok": True,
        "document": _process_result_to_dict(ready),
        "response": _rag_response_to_dict(response),
    }


@app.post("/api/qa/stream")
async def qa_stream(req: QARequest) -> StreamingResponse:
    if not req.doc_name and not req.pdf_path:
        raise HTTPException(status_code=400, detail="Either doc_name or pdf_path must be provided")

    async def work(emit: ProgressEmitter) -> dict[str, Any]:
        ready = await asyncio.to_thread(
            ensure_document_ready,
            doc=req.doc_name,
            pdf=req.pdf_path,
            force=req.force,
            model=req.model,
            toc_check_pages=req.toc_check_pages,
            max_pages_per_node=req.max_pages_per_node,
            max_tokens_per_node=req.max_tokens_per_node,
            if_add_node_id=req.if_add_node_id,
            if_add_node_summary=req.if_add_node_summary,
            if_add_node_text=req.if_add_node_text,
            if_add_doc_description=req.if_add_doc_description,
            structure_max_limit=req.structure_max_limit,
            content_chunk_size=req.content_chunk_size,
            progress_callback=emit,
        )
        emit({"type": "stage_done", "stage": "ensure_document_ready", "doc_name": ready.doc_name})
        response = await agentic_rag(
            query=req.query,
            doc_name=ready.doc_name,
            model=req.model,
            max_turns=req.max_turns,
            prompt_file=req.prompt_file or "specindex_system.txt",
            history_messages=req.history,
            enable_context_reuse=req.enable_context_reuse,
            context_session_id=req.context_session_id,
            progress_callback=emit,
        )
        return {
            "doc_name": ready.doc_name,
            "context_session_id": response.context_session_id,
            "process": _process_result_to_dict(ready),
            "response": _rag_response_to_dict(response),
        }

    return StreamingResponse(_stream_events(work), media_type="text/event-stream")


@app.get("/api/pdf/{doc_name}")
def get_pdf(doc_name: str) -> FileResponse:
    pdf_file = _resolve_pdf_file(doc_name)
    return FileResponse(
        pdf_file,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@app.get("/api/sessions")
def list_sessions() -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    for record in _iter_session_records():
        payload = record["payload"]
        sessions.append(
            {
                "id": record["id"],
                "timestamp": record["timestamp"],
                "doc_name": payload.get("doc_name", ""),
                "query": payload.get("query", ""),
                "title": payload.get("title", ""),
                "total_turns": payload.get("total_turns", 0),
                "pages_retrieved": payload.get("pages_retrieved", []),
                "context_session_id": payload.get("context_session_id"),
            }
        )
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    return _load_session_file(session_id)


@app.patch("/api/sessions/{session_id}/rename")
def rename_session(session_id: str, req: RenameRequest) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    payload = _load_session_file(session_id)
    payload["title"] = req.title.strip()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "id": Path(session_id).name, "title": payload["title"]}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    path.unlink()
    return {"ok": True, "id": Path(session_id).name}


@app.get("/api/conversations")
def list_conversations() -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in _iter_session_records():
        grouped.setdefault(record["conversation_id"], []).append(record)
    conversations = [
        _build_conversation_summary(conversation_id, records)
        for conversation_id, records in grouped.items()
    ]
    conversations.sort(key=lambda item: item["timestamp"], reverse=True)
    return {"conversations": conversations}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    records = _get_conversation_records(conversation_id)
    summary = _build_conversation_summary(records[0]["conversation_id"], records)
    summary["entries"] = [_build_conversation_entry(record) for record in records]
    return summary


@app.patch("/api/conversations/{conversation_id}/rename")
def rename_conversation(conversation_id: str, req: RenameRequest) -> dict[str, Any]:
    records = _get_conversation_records(conversation_id)
    title = req.title.strip()
    for record in records:
        payload = record["payload"]
        payload["title"] = title
        record["path"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "id": Path(conversation_id).name, "title": title}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, Any]:
    records = _get_conversation_records(conversation_id)
    for record in records:
        record["path"].unlink()
    return {"ok": True, "id": Path(conversation_id).name, "deleted": len(records)}


@app.post("/api/onboarding/stream")
async def onboarding_stream() -> StreamingResponse:
    async def work(_emit: ProgressEmitter) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail="Onboarding UI action is not wired in V7.")

    return StreamingResponse(_stream_events(work), media_type="text/event-stream")


@app.post("/api/orientation/stream")
async def orientation_stream() -> StreamingResponse:
    async def work(_emit: ProgressEmitter) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail="Orientation UI action is not wired in V7.")

    return StreamingResponse(_stream_events(work), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8000)
