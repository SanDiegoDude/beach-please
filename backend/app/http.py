"""Shared async HTTP client. One per process, polite User-Agent."""
from __future__ import annotations

import httpx

from app.config import get_settings

USER_AGENT = "BeachPlease/0.1 (https://github.com/local/beach-please vibe-code demo)"

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
