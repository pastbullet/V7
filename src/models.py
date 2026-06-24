"""Shared data models for the V7 Agentic RAG reading layer.

This file is intentionally small.  V7 brings back the M1 PageIndex-style reader
as a front end, but it does not import M1/V6's staged extraction IR models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A page citation extracted from a final answer."""

    doc_name: str
    page: int
    context: str = ""


class ToolCallRecord(BaseModel):
    """One executed tool call in the agent loop trace."""

    turn: int
    tool: str
    arguments: dict = Field(default_factory=dict)
    result_summary: str = ""


class TokenUsage(BaseModel):
    """Token usage reported by an LLM provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0


class ToolCall(BaseModel):
    """Provider-neutral tool call representation."""

    name: str
    arguments: dict = Field(default_factory=dict)
    id: str


class LLMResponse(BaseModel):
    """Provider-neutral response returned by ``LLMAdapter``."""

    has_tool_calls: bool = False
    tool_calls: list[ToolCall] = Field(default_factory=list)
    text: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_message: dict = Field(default_factory=dict)


class RAGResponse(BaseModel):
    """Final Agentic RAG answer plus the evidence navigation trace."""

    answer: str
    answer_clean: str = ""
    citations: list[Citation] = Field(default_factory=list)
    trace: list[ToolCallRecord] = Field(default_factory=list)
    pages_retrieved: list[int] = Field(default_factory=list)
    all_pages_requested: list[int] = Field(default_factory=list)
    total_turns: int = 0
    context_session_id: str | None = None
