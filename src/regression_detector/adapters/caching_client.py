"""Local response cache around any `LLMClient` (decisions 1.5, 1.6f-g; key and expiry 2026-11-17).

Only `completed` calls are stored, so re-running a run spends calls only on the
cases that did not complete. The cache is a development aid: CI starts with an
empty file and the "nothing changed" check bypasses it.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ValidationError

from regression_detector.adapters.sqlite_support import connect
from regression_detector.ports.llm import LLMClient, LLMRequest, LLMResult, LLMStatus, Usage

DEFAULT_CACHE_PATH = Path(".cache/llm-cache.sqlite")
DEFAULT_TTL = timedelta(days=7)

# Bumped whenever the serialization below changes, so old entries can never match.
CACHE_KEY_VERSION = "v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    requested_model TEXT NOT NULL,
    served_model TEXT,
    raw_text TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    reasoning_tokens INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    provider_request_id TEXT
) STRICT
"""


def utc_now() -> datetime:
    return datetime.now(UTC)


def request_key(request: LLMRequest[Any]) -> str:
    """Version prefix + sha256 of the canonical JSON of everything the model receives."""
    payload = {
        "model": request.model,
        "instructions": request.instructions,
        "few_shot_examples": [asdict(example) for example in request.few_shot_examples],
        "user_input": request.user_input,
        "output_schema": request.output_schema.model_json_schema(),
        "generation": asdict(request.generation),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_VERSION}:{digest}"


class SQLiteResponseCache:
    """Completed answers stored by request key in a local SQLite file."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH, ttl: timedelta = DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._connection = connect(path)
        with self._connection:
            self._connection.execute(SCHEMA)

    def get[T: BaseModel](
        self, key: str, request: LLMRequest[T], now: datetime
    ) -> LLMResult[T] | None:
        """The stored answer, or None when missing, expired or no longer valid for the schema."""
        row = self._connection.execute(
            "SELECT created_at, served_model, raw_text, input_tokens, cached_input_tokens,"
            " output_tokens, reasoning_tokens, latency_ms, provider_request_id"
            " FROM responses WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        created_at, served_model, raw_text, *tokens, latency_ms, request_id = row
        if now - datetime.fromisoformat(created_at) > self._ttl:
            return None
        try:
            parsed = request.output_schema.model_validate_json(raw_text)
        except ValidationError:
            return None
        return LLMResult(
            status=LLMStatus.COMPLETED,
            parsed=parsed,
            raw_text=raw_text,
            requested_model=request.model,
            served_model=served_model,
            usage=Usage(*tokens),
            latency_ms=latency_ms,
            provider_request_id=request_id,
            from_local_cache=True,
        )

    def put(self, key: str, result: LLMResult[Any], now: datetime) -> None:
        """Store a completed answer, replacing an expired entry with the same key."""
        if result.status != LLMStatus.COMPLETED or result.raw_text is None:
            raise ValueError("only completed calls with an answer are cached")
        usage = result.usage
        with self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    now.isoformat(),
                    result.requested_model,
                    result.served_model,
                    result.raw_text,
                    usage.input_tokens,
                    usage.cached_input_tokens,
                    usage.output_tokens,
                    usage.reasoning_tokens,
                    result.latency_ms,
                    result.provider_request_id,
                ),
            )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class CachingLLMClient:
    """An `LLMClient` that answers from the local cache when it can and fills it otherwise."""

    def __init__(
        self,
        inner: LLMClient,
        cache: SQLiteResponseCache,
        *,
        bypass: bool = False,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._bypass = bypass
        self._clock = clock

    async def complete[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        if self._bypass:
            return await self._inner.complete(request)
        key = request_key(request)
        cached = self._cache.get(key, request, self._clock())
        if cached is not None:
            return cached
        result = await self._inner.complete(request)
        if result.status == LLMStatus.COMPLETED and result.raw_text is not None:
            self._cache.put(key, result, self._clock())
        return result
