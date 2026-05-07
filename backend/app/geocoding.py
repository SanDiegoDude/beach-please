"""Live geocoding via OpenStreetMap Nominatim.

Any beach the user names that isn't in the static catalog gets geocoded on
the fly and added to an in-memory dynamic catalog so subsequent tool calls
work transparently.

Nominatim policy notes (we comply):
- Custom User-Agent identifying the app (set in app.http).
- Hard-cap: ~1 req/sec. We cache aggressively (24h) and serialize calls.
- Always include a "us" countrycodes filter to keep this scoped to US beaches.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.cache import get_cache
from app.catalog import Beach, slugify
from app.http import get_http_client

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_us_state_abbrev = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


_geocode_lock = asyncio.Lock()


def _state_from_address(addr: dict[str, Any]) -> str:
    state = addr.get("state") or ""
    return _us_state_abbrev.get(state.lower(), state[:2].upper() if state else "")


def _build_name(display: str) -> str:
    """Take just the first chunk of a Nominatim display_name as the friendly label."""
    parts = [p.strip() for p in display.split(",")]
    return parts[0] if parts else display


def _build_query(query: str) -> str:
    """Bias queries toward beaches without forcing it (Nominatim is fuzzy)."""
    q = query.strip()
    if not q:
        return q
    if not re.search(r"\bbeach\b|\bcove\b|\bisland\b|\bshore\b|\bstrand\b|\bpier\b", q, re.I):
        q = f"{q} beach"
    return q


async def geocode_beach(query: str) -> Beach | None:
    """Return a Beach record for a free-text query, geocoded live via Nominatim.

    Cached 24h. Serialized to respect Nominatim's 1 req/sec policy.
    """
    cache_key = f"geocode:{query.lower().strip()}"

    async def fetch() -> Beach | None:
        async with _geocode_lock:
            await asyncio.sleep(1.0)
            client = get_http_client()
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={
                        "q": _build_query(query),
                        "format": "jsonv2",
                        "addressdetails": "1",
                        "limit": "5",
                        "countrycodes": "us",
                    },
                )
                resp.raise_for_status()
                results = resp.json()
            except Exception:
                return None

        if not results:
            return None

        best = results[0]
        try:
            lat = float(best["lat"])
            lon = float(best["lon"])
        except (KeyError, ValueError):
            return None

        addr = best.get("address", {}) or {}
        state = _state_from_address(addr)
        display = best.get("display_name", query)
        name = _build_name(display)

        slug_base = slugify(f"{name} {state}".strip())
        if not slug_base:
            slug_base = slugify(name) or "geocoded-beach"

        region_parts = [p for p in [addr.get("county"), addr.get("state")] if p]
        region = ", ".join(region_parts) if region_parts else "Live geocoded"

        return Beach(
            slug=slug_base,
            name=name,
            state=state or "??",
            region=region,
            lat=lat,
            lon=lon,
            description=display,
            tags=["live-geocoded"],
        )

    return await get_cache().get_or_set(cache_key, fetch)
