from __future__ import annotations

import asyncio
import os
import random
import threading
import time
from functools import lru_cache
from typing import Any

from groq import AsyncGroq, Groq

DEFAULT_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "3"))
DEFAULT_BASE_DELAY_S = float(os.getenv("GROQ_RETRY_BASE_DELAY_S", "1.0"))
DEFAULT_MAX_DELAY_S = float(os.getenv("GROQ_RETRY_MAX_DELAY_S", "8.0"))
DEFAULT_SYNC_CONCURRENCY = int(os.getenv("GROQ_SYNC_CONCURRENCY", "2"))
DEFAULT_ASYNC_CONCURRENCY = int(os.getenv("GROQ_ASYNC_CONCURRENCY", "2"))

_sync_gate = threading.BoundedSemaphore(DEFAULT_SYNC_CONCURRENCY)
_async_gate = asyncio.Semaphore(DEFAULT_ASYNC_CONCURRENCY)


@lru_cache(maxsize=4)
def _sync_client(api_key: str | None) -> Groq:
    resolved_key = api_key or os.getenv("GROQ_API_KEY")
    if not resolved_key:
        raise ValueError("Groq API key is required. Set GROQ_API_KEY.")
    return Groq(api_key=resolved_key)


@lru_cache(maxsize=4)
def _async_client(api_key: str | None) -> AsyncGroq:
    resolved_key = api_key or os.getenv("GROQ_API_KEY")
    if not resolved_key:
        raise ValueError("Groq API key is required. Set GROQ_API_KEY.")
    return AsyncGroq(api_key=resolved_key)


def get_sync_client(api_key: str | None = None) -> Groq:
    return _sync_client(api_key)


def get_async_client(api_key: str | None = None) -> AsyncGroq:
    return _async_client(api_key)


def _error_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _error_message(exc: Exception) -> str:
    parts = [str(exc)]
    body = getattr(exc, "body", None)
    if body:
        parts.append(str(body))
    message = getattr(exc, "message", None)
    if message:
        parts.append(str(message))
    return " ".join(p for p in parts if p).strip()


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = _error_message(exc).lower()
    code = _error_status_code(exc)
    return code == 429 or "429" in msg or "rate_limit" in msg or "too many requests" in msg


def _is_retryable_error(exc: Exception) -> bool:
    if _is_rate_limit_error(exc):
        return True

    code = _error_status_code(exc)
    if code is not None and 500 <= code < 600:
        return True

    msg = _error_message(exc).lower()
    transient_markers = (
        "timeout",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "service unavailable",
        "internal server error",
        "bad gateway",
        "gateway timeout",
    )
    return any(marker in msg for marker in transient_markers)


def _backoff_seconds(attempt: int) -> float:
    capped = min(DEFAULT_MAX_DELAY_S, DEFAULT_BASE_DELAY_S * (2 ** (attempt - 1)))
    return capped + random.uniform(0, min(0.5, capped / 2))


def _wrap_terminal_error(exc: Exception) -> RuntimeError:
    if _is_rate_limit_error(exc):
        return RuntimeError("Groq rate limit (429) - wait and retry or upgrade quota.")
    return RuntimeError(f"Groq API error: {_error_message(exc)}")


def create_json_completion(
    *,
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    temperature: float = 0,
    api_key: str | None = None,
) -> str:
    client = get_sync_client(api_key)
    last_error: Exception | None = None

    for attempt in range(1, DEFAULT_MAX_RETRIES + 2):
        try:
            with _sync_gate:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as exc:
            last_error = exc
            if attempt > DEFAULT_MAX_RETRIES or not _is_retryable_error(exc):
                raise _wrap_terminal_error(exc) from exc
            time.sleep(_backoff_seconds(attempt))

    raise _wrap_terminal_error(last_error or RuntimeError("Unknown Groq error"))


async def create_streaming_completion(
    *,
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    temperature: float = 0.3,
    api_key: str | None = None,
):
    client = get_async_client(api_key)
    async with _async_gate:
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
