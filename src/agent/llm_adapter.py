"""LLM Adapter — 统一 OpenAI / Anthropic 的 tool calling 接口差异。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv

from src.models import LLMResponse, TokenUsage, ToolCall
from src.tools.schemas import convert_to_anthropic_format

load_dotenv(override=False)

DEFAULT_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
logger = logging.getLogger("llm")


class LLMOutputTruncatedError(RuntimeError):
    """Raised when an OpenAI-compatible completion is cut off by token limits."""


class _NullAsyncSemaphore:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class LLMAdapter:
    """统一 OpenAI/Anthropic 的 tool calling 接口。"""

    _limiters: dict[tuple[int, int], asyncio.Semaphore] = {}

    def __init__(self, provider: str, model: str):
        """
        Args:
            provider: "openai" 或 "anthropic"
            model: 模型名称，如 "gpt-4o", "claude-sonnet-4-20250514"
        """
        self.provider = provider
        self.model = model
        self._client = None
        self._openai_clients: dict[tuple[int, str | None, str | None, bool], Any] = {}
        self._openai_key_cursor = 0

    # ── lazy client init ──────────────────────────────────

    def _get_openai_client(self):
        if self._client is not None:
            return self._client

        from openai import AsyncOpenAI

        base_url = self._resolve_openai_base_url()
        key_index, api_key = self._select_openai_api_key(base_url)
        trust_env = self._openai_trust_env()
        cache_key = (key_index, api_key, base_url, trust_env)
        if cache_key not in self._openai_clients:
            timeout = float(os.getenv("PROTOCOL_TWIN_LLM_TIMEOUT_SEC", "120"))
            client_kwargs: dict[str, Any] = {
                "api_key": api_key,
                "base_url": base_url,
                "timeout": timeout,
            }
            if not trust_env:
                import httpx

                client_kwargs["http_client"] = httpx.AsyncClient(
                    timeout=timeout,
                    trust_env=False,
                )
            self._openai_clients[cache_key] = AsyncOpenAI(
                **client_kwargs,
            )
        return self._openai_clients[cache_key]

    def _get_anthropic_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                base_url=os.getenv("ANTHROPIC_BASE_URL"),
                timeout=float(os.getenv("PROTOCOL_TWIN_LLM_TIMEOUT_SEC", "120")),
            )
        return self._client

    def _openai_base_url(self) -> str:
        return (self._resolve_openai_base_url() or "").strip().lower()

    @staticmethod
    def _openai_trust_env() -> bool:
        return str(os.getenv("PROTOCOL_TWIN_OPENAI_TRUST_ENV", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _is_qwen_model(self) -> bool:
        return (self.model or "").strip().lower().startswith("qwen")

    def _is_deepseek_model(self) -> bool:
        return (self.model or "").strip().lower().startswith("deepseek")

    @staticmethod
    def _is_siliconflow_base_url(base_url: str | None) -> bool:
        return "siliconflow" in str(base_url or "").strip().lower()

    @staticmethod
    def _is_dashscope_base_url(base_url: str | None) -> bool:
        return "dashscope" in str(base_url or "").strip().lower()

    @staticmethod
    def _is_deepseek_base_url(base_url: str | None) -> bool:
        return "deepseek" in str(base_url or "").strip().lower()

    def _resolve_openai_base_url(self) -> str | None:
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        siliconflow_base_url = os.getenv("SILICONFLOW_BASE_URL")
        siliconflow_key = os.getenv("SILICONFLOW_API_KEY")
        dashscope_base_url = os.getenv("DASHSCOPE_BASE_URL")
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if self._is_qwen_model():
            if self._is_siliconflow_base_url(openai_base_url) or self._is_dashscope_base_url(
                openai_base_url
            ):
                return openai_base_url
            if siliconflow_base_url or siliconflow_key:
                return siliconflow_base_url or DEFAULT_SILICONFLOW_BASE_URL
            if dashscope_base_url or dashscope_key:
                return dashscope_base_url or DEFAULT_DASHSCOPE_BASE_URL
        if self._is_deepseek_model() and not openai_base_url:
            if deepseek_base_url or deepseek_key:
                return deepseek_base_url or DEFAULT_DEEPSEEK_BASE_URL
        return openai_base_url or siliconflow_base_url or dashscope_base_url or deepseek_base_url

    def _resolve_openai_api_key(self, base_url: str | None = None) -> str | None:
        siliconflow_key = os.getenv("SILICONFLOW_API_KEY")
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        resolved_base_url = base_url or self._resolve_openai_base_url()
        if self._is_siliconflow_base_url(resolved_base_url):
            return siliconflow_key or os.getenv("OPENAI_API_KEY")
        if self._is_dashscope_base_url(resolved_base_url):
            return dashscope_key or os.getenv("OPENAI_API_KEY")
        if self._is_deepseek_base_url(resolved_base_url):
            return deepseek_key or os.getenv("OPENAI_API_KEY")
        if self._is_qwen_model():
            return siliconflow_key or dashscope_key or os.getenv("OPENAI_API_KEY")
        if self._is_deepseek_model():
            return deepseek_key or os.getenv("OPENAI_API_KEY")
        return os.getenv("OPENAI_API_KEY") or siliconflow_key or dashscope_key or deepseek_key

    @staticmethod
    def _split_openai_api_keys(raw: str | None) -> list[str]:
        return [
            item.strip()
            for item in re.split(r"[,\n;]+", raw or "")
            if item.strip()
        ]

    def _resolve_openai_api_keys(self, base_url: str | None = None) -> list[str]:
        pooled = self._split_openai_api_keys(os.getenv("OPENAI_API_KEYS"))
        if pooled:
            return pooled
        single = self._resolve_openai_api_key(base_url)
        return [single] if single else []

    def _select_openai_api_key(self, base_url: str | None = None) -> tuple[int, str | None]:
        keys = self._resolve_openai_api_keys(base_url)
        if not keys:
            return 0, None
        index = self._openai_key_cursor % len(keys)
        self._openai_key_cursor = (index + 1) % len(keys)
        return index, keys[index]

    def _openai_gateway_profile(self) -> str:
        base_url = self._openai_base_url()
        if "api.bltcy.ai" in base_url:
            return "bltcy"
        if "shell.wyzai.top" in base_url:
            return "wyzai"
        if "packyapi.com" in base_url:
            return "packyapi"
        if self._is_deepseek_base_url(base_url):
            return "deepseek"
        return "default"

    def _supports_forced_tool_choice(self) -> bool:
        return self._openai_gateway_profile() not in {"bltcy", "deepseek", "packyapi", "wyzai"}

    def _supports_json_schema_response_format(self) -> bool:
        return self._openai_gateway_profile() not in {"bltcy", "deepseek", "packyapi"}

    def _supports_json_object_response_format(self) -> bool:
        return self._openai_gateway_profile() not in {"packyapi"}

    @staticmethod
    def _parse_positive_int_env(name: str) -> int | None:
        raw = str(os.getenv(name, "")).strip()
        if not raw:
            return None
        value = int(raw)
        if value <= 0:
            raise ValueError(f"{name} must be a positive integer, got {raw!r}")
        return value

    def _resolve_openai_max_tokens(self) -> int | None:
        explicit = self._parse_positive_int_env("PROTOCOL_TWIN_OPENAI_MAX_TOKENS")
        if explicit is not None:
            return explicit

        base_url = self._openai_base_url()
        if self._is_siliconflow_base_url(base_url):
            return self._parse_positive_int_env("SILICONFLOW_MAX_OUTPUT_TOKENS")
        if self._is_dashscope_base_url(base_url):
            return self._parse_positive_int_env("DASHSCOPE_MAX_OUTPUT_TOKENS") or 8192
        return None

    def _raise_if_openai_output_truncated(
        self,
        choice,
        response,
        *,
        tools: list[dict],
        response_format: dict[str, Any] | None,
    ) -> None:
        finish_reason = str(getattr(choice, "finish_reason", "") or "").strip().lower()
        if finish_reason != "length":
            return

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        message = getattr(choice, "message", None)
        preview = str(getattr(message, "content", "") or "").strip().replace("\n", " ")
        preview = preview[:200]
        response_format_type = (
            str(response_format.get("type", "")).strip()
            if isinstance(response_format, dict)
            else "none"
        )
        raise LLMOutputTruncatedError(
            "OpenAI-compatible completion was truncated by the provider output limit. "
            f"model={self.model}, prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, "
            f"max_tokens={self._resolve_openai_max_tokens() or 'default'}, "
            f"response_format={response_format_type}, tools={bool(tools)}, preview={preview!r}"
        )

    # ── public API ────────────────────────────────────────

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        """统一的 LLM 调用接口。

        Args:
            messages: 消息列表（统一格式，含 system / user / assistant / tool）
            tools: Tool Schema 列表（OpenAI function calling 格式，内部自动转换）

        Returns:
            LLMResponse 统一响应结构
        """
        max_retries = self._resolve_llm_max_retries()
        attempt = 0
        while True:
            try:
                async with self._global_inflight_limiter():
                    timeout = self._resolve_llm_call_timeout()
                    if timeout is not None:
                        return await asyncio.wait_for(
                            self._chat_with_tools_once(messages, tools),
                            timeout=timeout,
                        )
                    return await self._chat_with_tools_once(messages, tools)
            except Exception as exc:
                if attempt >= max_retries or not self._is_retryable_infra_error(exc):
                    raise
                delay = self._retry_delay_seconds(exc, attempt=attempt)
                logger.warning(
                    "Retrying LLM call after retryable infrastructure error model=%s attempt=%s/%s delay=%.2fs error=%s",
                    self.model,
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                attempt += 1
                if delay > 0:
                    await asyncio.sleep(delay)

    async def _chat_with_tools_once(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        if self.provider == "openai":
            return await self._chat_openai(messages, tools)
        if self.provider == "anthropic":
            return await self._chat_anthropic(messages, tools)
        raise ValueError(f"Unsupported provider: {self.provider}")

    @classmethod
    def _reset_global_limiter_for_tests(cls) -> None:
        cls._limiters.clear()

    @staticmethod
    def _parse_nonnegative_int_env(name: str, default: int) -> int:
        raw = str(os.getenv(name, "")).strip()
        if not raw:
            return default
        value = int(raw)
        if value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {raw!r}")
        return value

    @staticmethod
    def _parse_positive_float_env(name: str) -> float | None:
        raw = str(os.getenv(name, "")).strip()
        if not raw:
            return None
        value = float(raw)
        if value <= 0:
            raise ValueError(f"{name} must be a positive number, got {raw!r}")
        return value

    @classmethod
    def _resolve_llm_max_inflight(cls) -> int:
        return cls._parse_nonnegative_int_env("PROTOCOL_TWIN_LLM_MAX_INFLIGHT", 5)

    @classmethod
    def _global_inflight_limiter(cls) -> asyncio.Semaphore:
        limit = cls._resolve_llm_max_inflight()
        if limit <= 0:
            return _NullAsyncSemaphore()
        loop = asyncio.get_running_loop()
        key = (id(loop), limit)
        limiter = cls._limiters.get(key)
        if limiter is None:
            limiter = asyncio.Semaphore(limit)
            cls._limiters[key] = limiter
        return limiter

    @classmethod
    def _resolve_llm_max_retries(cls) -> int:
        return cls._parse_nonnegative_int_env("PROTOCOL_TWIN_LLM_MAX_RETRIES", 0)

    @classmethod
    def _resolve_llm_call_timeout(cls) -> float | None:
        return cls._parse_positive_float_env("PROTOCOL_TWIN_LLM_CALL_TIMEOUT_SEC")

    @staticmethod
    def _exception_status_code(exc: Exception) -> int | None:
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            return status
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
        return None

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> float | None:
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is None:
            response = getattr(exc, "response", None)
            headers = getattr(response, "headers", None)
            if headers is not None:
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after is None:
            return None
        try:
            value = float(retry_after)
        except (TypeError, ValueError):
            return None
        return max(0.0, value)

    @classmethod
    def _is_retryable_infra_error(cls, exc: Exception) -> bool:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
            return True
        status = cls._exception_status_code(exc)
        if status in {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}:
            return True
        text = str(exc).lower()
        retryable_hints = (
            "timeout",
            "timed out",
            "connection error",
            "connection reset",
            "connection aborted",
            "server disconnected",
            "temporarily unavailable",
            "rate limit",
            "too many requests",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
            "origin_response_timeout",
            "error 524",
        )
        return any(hint in text for hint in retryable_hints)

    @classmethod
    def _retry_delay_seconds(cls, exc: Exception, *, attempt: int) -> float:
        retry_after = cls._retry_after_seconds(exc)
        if retry_after is not None:
            return retry_after
        base = cls._parse_positive_float_env("PROTOCOL_TWIN_LLM_RETRY_BASE_SEC") or 1.0
        cap = cls._parse_positive_float_env("PROTOCOL_TWIN_LLM_RETRY_MAX_SEC") or 30.0
        delay = min(cap, base * (2 ** max(0, attempt)))
        return delay + random.uniform(0, delay * 0.25)

    async def complete(
        self,
        prompt: str,
        *,
        timeout: float | None = None,
    ) -> str:
        """Thin convenience wrapper for single-turn text completion.

        Builds a single user message and returns the response text.
        Used by sketch.py / coverage_verifier.py / repair.py which only
        need plain-text I/O without tool calling.
        """
        messages = [{"role": "user", "content": prompt}]
        if timeout is not None:
            response = await asyncio.wait_for(
                self.chat_with_tools(messages=messages, tools=[]),
                timeout=timeout,
            )
        else:
            response = await self.chat_with_tools(messages=messages, tools=[])
        return response.text or ""

    def make_tool_result_message(self, tool_call_id: str, result: dict) -> dict:
        """构造 provider 特定的 tool result 消息。

        OpenAI:    {"role": "tool", "tool_call_id": ..., "content": ...}
        Anthropic: {"role": "user", "content": [{"type": "tool_result", ...}]}
        """
        content = json.dumps(result, ensure_ascii=False)
        if self.provider == "openai":
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        else:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": content,
                    }
                ],
            }

    # ── OpenAI implementation ─────────────────────────────

    async def _chat_openai(
        self, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        if self._should_route_openai_to_responses(messages, tools):
            return await self._chat_openai_via_responses(messages)

        if self._should_use_structured_output(messages, tools):
            return await self._chat_openai_structured(messages)

        return await self._chat_openai_once(messages, tools)

    async def _chat_openai_once(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        response_format: dict[str, Any] | None = None,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> LLMResponse:
        client = self._get_openai_client()

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        max_tokens = self._resolve_openai_max_tokens()
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        started_at = time.perf_counter()
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            duration_sec = time.perf_counter() - started_at
            self._log_llm_call(
                path="chat.completions",
                duration_sec=duration_sec,
                tools=bool(tools),
                response_format=response_format,
                error=exc,
            )
            if self._should_fallback_to_responses(exc, tools, response_format, tool_choice):
                return await self._chat_openai_via_responses(messages)
            raise
        stream_text_response = self._coerce_openai_stream_text_response(
            response,
            tools=tools,
            response_format=response_format,
        )
        if stream_text_response is not None:
            self._log_llm_call(
                path="chat.completions",
                duration_sec=time.perf_counter() - started_at,
                tools=bool(tools),
                response_format=response_format,
                usage=stream_text_response.usage,
            )
            return stream_text_response
        self._validate_openai_response_shape(response)
        choice = response.choices[0]
        self._raise_if_openai_output_truncated(
            choice,
            response,
            tools=tools,
            response_format=response_format,
        )
        msg = choice.message

        # Parse tool calls
        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(
                    ToolCall(
                        name=tc.function.name,
                        arguments=args,
                        id=tc.id,
                    )
                )

        # Build raw_message for appending back to messages list
        raw: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            raw["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": (
                            tc.function.arguments
                            if isinstance(tc.function.arguments, str)
                            else json.dumps(tc.function.arguments, ensure_ascii=False)
                        ),
                    },
                }
                for tc in msg.tool_calls
            ]

        # Token usage
        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
            )
        self._log_llm_call(
            path="chat.completions",
            duration_sec=time.perf_counter() - started_at,
            tools=bool(tools),
            response_format=response_format,
            usage=usage,
        )

        return LLMResponse(
            has_tool_calls=len(tool_calls) > 0,
            tool_calls=tool_calls,
            text=msg.content or None,
            usage=usage,
            raw_message=raw,
        )

    def _coerce_openai_stream_text_response(
        self,
        response,
        *,
        tools: list[dict],
        response_format: dict[str, Any] | None,
    ) -> LLMResponse | None:
        """Parse SSE text returned by broken OpenAI-compatible chat endpoints.

        Some gateways return a raw ``data: {...}`` stream even when the SDK call
        asked for a non-streaming ChatCompletion. The rest of this adapter
        expects the final merged ChatCompletion shape, so merge content/tool
        deltas here and keep the public LLMResponse contract unchanged.
        """

        if not isinstance(response, str):
            return None

        chunks = self._parse_openai_sse_json_chunks(response)
        if not chunks:
            return None

        content_parts: list[str] = []
        tool_call_parts: dict[int, dict[str, str]] = {}
        finish_reason = ""
        usage = TokenUsage()

        for chunk in chunks:
            chunk_usage = chunk.get("usage")
            if isinstance(chunk_usage, dict):
                usage = TokenUsage(
                    prompt_tokens=int(chunk_usage.get("prompt_tokens") or 0),
                    completion_tokens=int(chunk_usage.get("completion_tokens") or 0),
                )

            choices = chunk.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                if choice.get("finish_reason") is not None:
                    finish_reason = str(choice.get("finish_reason") or "")

                delta = choice.get("delta") or {}
                if not isinstance(delta, dict):
                    continue

                content = delta.get("content")
                if isinstance(content, str):
                    content_parts.append(content)

                delta_tool_calls = delta.get("tool_calls")
                if isinstance(delta_tool_calls, list):
                    self._merge_openai_stream_tool_call_deltas(tool_call_parts, delta_tool_calls)

        text = "".join(content_parts)
        raw: dict = {"role": "assistant", "content": text}
        tool_calls: list[ToolCall] = []
        raw_tool_calls: list[dict] = []

        for index in sorted(tool_call_parts):
            item = tool_call_parts[index]
            name = item.get("name", "")
            if not name:
                continue
            arguments_text = item.get("arguments", "").strip() or "{}"
            arguments = json.loads(arguments_text)
            tool_id = item.get("id") or f"call_{index}"
            tool_calls.append(
                ToolCall(
                    name=name,
                    arguments=arguments,
                    id=tool_id,
                )
            )
            raw_tool_calls.append(
                {
                    "id": tool_id,
                    "type": item.get("type") or "function",
                    "function": {
                        "name": name,
                        "arguments": arguments_text,
                    },
                }
            )

        if raw_tool_calls:
            raw["tool_calls"] = raw_tool_calls

        fake_choice = SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(content=text),
        )
        fake_response = SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )
        )
        self._raise_if_openai_output_truncated(
            fake_choice,
            fake_response,
            tools=tools,
            response_format=response_format,
        )

        return LLMResponse(
            has_tool_calls=bool(tool_calls),
            tool_calls=tool_calls,
            text=text or None,
            usage=usage,
            raw_message=raw,
        )

    @staticmethod
    def _parse_openai_sse_json_chunks(response_text: str) -> list[dict[str, Any]]:
        payloads: list[str] = []
        current_payload: list[str] = []
        saw_data_line = False

        for raw_line in response_text.splitlines():
            line = raw_line.rstrip("\r")
            if not line:
                if current_payload:
                    payloads.append("\n".join(current_payload))
                    current_payload = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                saw_data_line = True
                current_payload.append(line[5:].lstrip())

        if current_payload:
            payloads.append("\n".join(current_payload))

        if not saw_data_line:
            return []

        chunks: list[dict[str, Any]] = []
        for payload in payloads:
            payload = payload.strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                preview = payload.replace("\n", " ")[:200]
                raise RuntimeError(
                    "OpenAI-compatible endpoint returned malformed SSE ChatCompletion "
                    f"payload: {preview}"
                ) from exc
            if isinstance(parsed, dict):
                chunks.append(parsed)
        return chunks

    @staticmethod
    def _merge_openai_stream_tool_call_deltas(
        tool_call_parts: dict[int, dict[str, str]],
        delta_tool_calls: list,
    ) -> None:
        for tool_delta in delta_tool_calls:
            if not isinstance(tool_delta, dict):
                continue
            if "index" in tool_delta:
                try:
                    index = int(tool_delta.get("index"))
                except (TypeError, ValueError):
                    index = len(tool_call_parts)
            elif len(tool_call_parts) == 1:
                index = next(iter(tool_call_parts))
            else:
                index = len(tool_call_parts)

            item = tool_call_parts.setdefault(
                index,
                {"id": "", "type": "function", "name": "", "arguments": ""},
            )
            if isinstance(tool_delta.get("id"), str):
                item["id"] = tool_delta["id"]
            if isinstance(tool_delta.get("type"), str):
                item["type"] = tool_delta["type"]

            function = tool_delta.get("function")
            if not isinstance(function, dict):
                continue
            if isinstance(function.get("name"), str):
                item["name"] += function["name"]
            if isinstance(function.get("arguments"), str):
                item["arguments"] += function["arguments"]

    async def _chat_openai_via_responses(self, messages: list[dict]) -> LLMResponse:
        """Fallback path for gateways that support model on /responses but not /chat/completions."""

        client = self._get_openai_client()
        system_text, non_system_messages = self._split_system_messages(messages)
        transcript_lines: list[str] = []
        if system_text:
            transcript_lines.append("SYSTEM:")
            transcript_lines.append(system_text)
            transcript_lines.append("")
        for msg in non_system_messages:
            role = str(msg.get("role", "")).strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                content_text = json.dumps(content, ensure_ascii=False)
            else:
                content_text = str(content)
            transcript_lines.append(f"{role.upper()}:")
            transcript_lines.append(content_text)
            transcript_lines.append("")

        transcript = "\n".join(transcript_lines).strip()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": transcript or "",
        }

        started_at = time.perf_counter()
        try:
            response = await client.responses.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            self._log_llm_call(
                path="responses",
                duration_sec=time.perf_counter() - started_at,
                tools=False,
                response_format=None,
                error=exc,
            )
            raise

        response_text = getattr(response, "output_text", None)
        if not response_text:
            parts: list[str] = []
            for item in getattr(response, "output", []) or []:
                for block in getattr(item, "content", []) or []:
                    block_text = getattr(block, "text", None)
                    if isinstance(block_text, str) and block_text:
                        parts.append(block_text)
            response_text = "\n".join(parts) if parts else None

        usage_obj = getattr(response, "usage", None)
        usage = TokenUsage()
        if usage_obj is not None:
            usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "input_tokens", 0) or 0,
                completion_tokens=getattr(usage_obj, "output_tokens", 0) or 0,
            )
        self._log_llm_call(
            path="responses",
            duration_sec=time.perf_counter() - started_at,
            tools=False,
            response_format=None,
            usage=usage,
        )

        raw = {"role": "assistant", "content": response_text or ""}
        return LLMResponse(
            has_tool_calls=False,
            tool_calls=[],
            text=response_text,
            usage=usage,
            raw_message=raw,
        )

    async def _chat_openai_structured(
        self,
        messages: list[dict],
    ) -> LLMResponse:
        schema = self._structured_output_schema(messages)
        last_error: Exception | None = None

        if schema is not None:
            if self._supports_forced_tool_choice():
                synthetic_tools = [self._structured_output_tool_schema(schema)]
                try:
                    tool_response = await self._chat_openai_once(
                        messages,
                        synthetic_tools,
                        tool_choice={
                            "type": "function",
                            "function": {"name": self._structured_output_tool_name()},
                        },
                    )
                    normalized = self._normalize_structured_tool_response(tool_response)
                    if normalized is not None:
                        return normalized
                    if self._response_text_is_json_object(tool_response):
                        return tool_response
                except LLMOutputTruncatedError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

            if self._supports_json_schema_response_format():
                try:
                    schema_response = await self._chat_openai_once(
                        messages,
                        [],
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "structured_output",
                                "strict": True,
                                "schema": schema,
                            },
                        },
                    )
                    if self._response_text_is_json_object(schema_response):
                        return schema_response
                except LLMOutputTruncatedError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

        if self._supports_json_object_response_format():
            try:
                json_object_response = await self._chat_openai_once(
                    messages,
                    [],
                    response_format={"type": "json_object"},
                )
                if self._response_text_is_json_object(json_object_response):
                    return json_object_response
            except LLMOutputTruncatedError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        try:
            return await self._chat_openai_once(messages, [])
        except Exception as exc:
            if isinstance(exc, LLMOutputTruncatedError):
                raise
            if last_error is not None:
                raise last_error
            raise

    # ── Anthropic implementation ──────────────────────────

    async def _chat_anthropic(
        self, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        client = self._get_anthropic_client()

        # Split system messages out — Anthropic uses a separate `system` param
        system_text, non_system_messages = self._split_system_messages(messages)

        # Convert tool schemas from OpenAI format to Anthropic format
        anthropic_tools = convert_to_anthropic_format(tools) if tools else []

        kwargs: dict = {
            "model": self.model,
            "messages": non_system_messages,
            "max_tokens": 4096,
        }
        if system_text:
            kwargs["system"] = system_text
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        started_at = time.perf_counter()
        response = await client.messages.create(**kwargs)

        # Parse tool calls from content blocks
        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []

        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                        id=block.id,
                    )
                )
            elif block.type == "text":
                text_parts.append(block.text)

        combined_text = "\n".join(text_parts) if text_parts else None

        # Build raw_message for Anthropic (serialize content blocks)
        raw: dict = {
            "role": "assistant",
            "content": [
                self._serialize_anthropic_block(b) for b in response.content
            ],
        }

        # Token usage
        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens or 0,
            completion_tokens=response.usage.output_tokens or 0,
        )
        self._log_llm_call(
            path="anthropic.messages",
            duration_sec=time.perf_counter() - started_at,
            tools=bool(anthropic_tools),
            response_format=None,
            usage=usage,
        )

        return LLMResponse(
            has_tool_calls=len(tool_calls) > 0,
            tool_calls=tool_calls,
            text=combined_text,
            usage=usage,
            raw_message=raw,
        )

    # ── helpers ───────────────────────────────────────────

    @staticmethod
    def _split_system_messages(
        messages: list[dict],
    ) -> tuple[str, list[dict]]:
        """Extract system messages into a single string; return the rest."""
        system_parts: list[str] = []
        rest: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                rest.append(msg)
        return "\n".join(system_parts), rest

    def _log_llm_call(
        self,
        *,
        path: str,
        duration_sec: float,
        tools: bool,
        response_format: dict[str, Any] | None,
        usage: TokenUsage | None = None,
        error: Exception | None = None,
    ) -> None:
        response_format_type = (
            str(response_format.get("type", "")).strip()
            if isinstance(response_format, dict)
            else "none"
        )
        prompt_tokens = usage.prompt_tokens if usage is not None else 0
        completion_tokens = usage.completion_tokens if usage is not None else 0
        message = (
            "LLM call %s model=%s duration=%.2fs tools=%s response_format=%s prompt_tokens=%s completion_tokens=%s"
        )
        args = (
            path,
            self.model,
            duration_sec,
            tools,
            response_format_type,
            prompt_tokens,
            completion_tokens,
        )
        if error is None:
            logger.info(message, *args)
        else:
            logger.warning(message + " error=%s", *args, error)

    @staticmethod
    def _should_request_json_object(messages: list[dict], tools: list[dict]) -> bool:
        """Backward-compatible alias for tests and legacy callers."""
        return LLMAdapter._should_use_structured_output(messages, tools)

    @staticmethod
    def _should_use_structured_output(messages: list[dict], tools: list[dict]) -> bool:
        """Use structured-output enforcement for plain JSON-only prompts."""
        if tools:
            return False
        for msg in messages:
            if msg.get("role") != "system":
                continue
            content = str(msg.get("content", ""))
            if "Return JSON only" in content or "Return JSON only with this schema" in content:
                return True
        return False

    @staticmethod
    def _messages_include_images(messages: list[dict]) -> bool:
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = str(part.get("type", "")).strip().lower()
                if part_type in {"image", "image_url"}:
                    return True
        return False

    @staticmethod
    def _extract_first_json_object(text: str) -> dict[str, Any] | None:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    @staticmethod
    def _infer_json_schema_from_example(value: Any) -> dict[str, Any]:
        if isinstance(value, bool):
            return {"type": "boolean"}
        if isinstance(value, int) and not isinstance(value, bool):
            return {"type": "integer"}
        if isinstance(value, float):
            return {"type": "number"}
        if isinstance(value, str):
            return {"type": "string"}
        if value is None:
            return {"type": "null"}
        if isinstance(value, list):
            item_schema = (
                LLMAdapter._infer_json_schema_from_example(value[0])
                if value else
                {}
            )
            return {"type": "array", "items": item_schema}
        if isinstance(value, dict):
            properties = {
                key: LLMAdapter._infer_json_schema_from_example(item)
                for key, item in value.items()
            }
            return {
                "type": "object",
                "properties": properties,
                "required": list(value.keys()),
                "additionalProperties": False,
            }
        return {}

    @classmethod
    def _structured_output_schema(cls, messages: list[dict]) -> dict[str, Any] | None:
        for msg in messages:
            if msg.get("role") != "system":
                continue
            content = str(msg.get("content", ""))
            example = cls._extract_first_json_object(content)
            if isinstance(example, dict):
                return cls._infer_json_schema_from_example(example)
        return {
            "type": "object",
            "additionalProperties": True,
        }

    @staticmethod
    def _structured_output_tool_name() -> str:
        return "emit_structured_response"

    @classmethod
    def _structured_output_tool_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cls._structured_output_tool_name(),
                "description": "Return the structured JSON response exactly once.",
                "parameters": schema,
            },
        }

    @classmethod
    def _normalize_structured_tool_response(cls, response: LLMResponse) -> LLMResponse | None:
        if not response.tool_calls:
            return None
        first_call = response.tool_calls[0]
        if first_call.name != cls._structured_output_tool_name():
            return None
        if not isinstance(first_call.arguments, dict):
            return None
        return LLMResponse(
            has_tool_calls=False,
            tool_calls=[],
            text=json.dumps(first_call.arguments, ensure_ascii=False),
            usage=response.usage,
            raw_message=response.raw_message,
        )

    @staticmethod
    def _response_text_is_json_object(response: LLMResponse) -> bool:
        text = (response.text or "").strip()
        if not text:
            return False
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict)

    @staticmethod
    def _validate_openai_response_shape(response) -> None:
        """Fail clearly when a gateway returns HTML/plain text instead of ChatCompletion."""
        choices = getattr(response, "choices", None)
        if isinstance(choices, list) and choices:
            return

        preview = response if isinstance(response, str) else repr(response)
        preview = preview.strip().replace("\n", " ")[:200]
        raise RuntimeError(
            "OpenAI-compatible endpoint returned a non-ChatCompletion payload. "
            f"Expected `.choices`, got {type(response).__name__}. "
            f"Preview: {preview}"
        )

    def _should_fallback_to_responses(
        self,
        exc: Exception,
        tools: list[dict],
        response_format: dict[str, Any] | None,
        tool_choice: dict[str, Any] | str | None,
    ) -> bool:
        """Enable /responses fallback for specific model/gateway combinations."""

        if not self._responses_api_enabled():
            return False
        if tools or response_format is not None or tool_choice is not None:
            return False
        model = (self.model or "").strip().lower()
        if not model.startswith("gpt-5.4"):
            return False

        message = str(exc).lower()
        fallback_hints = (
            "server disconnected without sending a response",
            "empty reply from server",
            "invalid param: not support for model",
            "connection error",
        )
        return any(hint in message for hint in fallback_hints)

    def _should_route_openai_to_responses(self, messages: list[dict], tools: list[dict]) -> bool:
        """Use /responses directly for models/gateways known to be unreliable on chat/completions."""

        if not self._responses_api_enabled():
            return False
        if tools:
            return False
        if self._should_use_structured_output(messages, tools):
            return False
        model = (self.model or "").strip().lower()
        return model.startswith("gpt-5.4")

    @staticmethod
    def _responses_api_enabled() -> bool:
        return str(os.getenv("PROTOCOL_TWIN_OPENAI_ENABLE_RESPONSES", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _serialize_anthropic_block(block) -> dict:
        """Convert an Anthropic ContentBlock to a plain dict."""
        if block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        elif block.type == "text":
            return {"type": "text", "text": block.text}
        # fallback
        return {"type": block.type}
