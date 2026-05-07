"""Tiny in-memory TTL cache so the demo stays snappy and free APIs stay happy."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import get_settings


class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(self, key: str, producer: Callable[[], Awaitable[Any]]) -> Any:
        now = time.time()
        async with self._lock:
            cached = self._store.get(key)
            if cached and now - cached[0] < self._ttl:
                return cached[1]
        value = await producer()
        async with self._lock:
            self._store[key] = (time.time(), value)
        return value


_cache: TTLCache | None = None


def get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(ttl_seconds=get_settings().cache_ttl_seconds)
    return _cache
