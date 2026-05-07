"""Rip current risk forecast from NOAA NWS Surf Zone Forecast (SRF) text product.

Flow:
1. Resolve the beach's NWS forecast zone + county warning area (CWA) once.
2. Fetch the latest SRF product issued by that CWA.
3. Find the section for the matching zone and pull "Rip Current Risk".
"""
from __future__ import annotations

import re
from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug
from app.http import get_http_client

NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
SRF_LIST_URL = "https://api.weather.gov/products/types/SRF/locations/{cwa}"
SRF_PRODUCT_URL = "https://api.weather.gov/products/{product_id}"

RISK_LINE = re.compile(
    r"Rip\s+Current\s+Risk\*?\.+\s*(Low|Moderate|High)",
    re.IGNORECASE,
)


def _normalize(raw: str) -> str:
    t = raw.strip().lower()
    if "high" in t:
        return "High"
    if "mod" in t:
        return "Moderate"
    if "low" in t:
        return "Low"
    return raw.title()


async def _resolve_zone_cwa(lat: float, lon: float) -> tuple[str | None, str | None]:
    client = get_http_client()
    try:
        resp = await client.get(NWS_POINTS_URL.format(lat=lat, lon=lon))
        resp.raise_for_status()
        props = resp.json().get("properties", {})
    except Exception:
        return None, None
    zone_url = props.get("forecastZone") or ""
    zone = zone_url.rsplit("/", 1)[-1] if zone_url else None
    cwa = props.get("cwa")
    return zone, cwa


async def _latest_srf_text(cwa: str) -> str | None:
    client = get_http_client()
    try:
        listing = await client.get(SRF_LIST_URL.format(cwa=cwa))
        listing.raise_for_status()
        items = listing.json().get("@graph", []) or []
        if not items:
            return None
        product = await client.get(SRF_PRODUCT_URL.format(product_id=items[0]["id"]))
        product.raise_for_status()
        return product.json().get("productText")
    except Exception:
        return None


def _extract_zone_section(text: str, zone: str) -> str | None:
    """Find the chunk of the SRF that starts with the given zone code header.

    SRF sections look like:
        CAZ552-071015-
        Orange County Coastal Areas-
        ...
        Rip Current Risk*.............Low.
    Sections end at $$ or the next zone header.
    """
    pattern = re.compile(
        rf"{re.escape(zone)}[-A-Z0-9]*-\s*\n.*?(?=\n[A-Z]{{2,}}Z\d{{3}}[-A-Z0-9]*-\s*\n|\$\$|\Z)",
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(0) if match else None


async def get_rip_current_risk(beach_slug: str) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    async def fetch() -> dict[str, Any]:
        zone, cwa = await _resolve_zone_cwa(beach.lat, beach.lon)
        if not cwa:
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "available": False,
                "risk": "Unknown",
                "note": "Could not resolve NWS CWA for this beach.",
            }

        srf = await _latest_srf_text(cwa)
        if not srf:
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "available": False,
                "risk": "Unknown",
                "office": cwa,
                "note": f"No recent Surf Zone Forecast issued by {cwa}.",
            }

        section = _extract_zone_section(srf, zone) if zone else None
        search_text = section or srf
        match = RISK_LINE.search(search_text)
        if not match:
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "available": False,
                "risk": "Unknown",
                "office": cwa,
                "note": "Surf Zone Forecast did not include a Rip Current Risk line for this zone.",
            }

        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "available": True,
            "risk": _normalize(match.group(1)),
            "office": cwa,
            "zone": zone,
            "source": "NOAA NWS Surf Zone Forecast",
        }

    return await get_cache().get_or_set(f"rip:{beach.slug}", fetch)
