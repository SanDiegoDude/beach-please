"""Active NWS alerts (Beach Hazards, Rip Current, High Surf, etc.) for a point."""
from __future__ import annotations

from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug
from app.http import get_http_client

NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"

RELEVANT_EVENTS = {
    "Beach Hazards Statement",
    "Rip Current Statement",
    "High Surf Advisory",
    "High Surf Warning",
    "Coastal Flood Advisory",
    "Coastal Flood Warning",
    "Coastal Flood Statement",
    "Tropical Storm Watch",
    "Tropical Storm Warning",
    "Hurricane Watch",
    "Hurricane Warning",
    "Tsunami Advisory",
    "Tsunami Warning",
    "Small Craft Advisory",
}


async def get_active_alerts(beach_slug: str) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    async def fetch() -> dict[str, Any]:
        params = {"point": f"{beach.lat},{beach.lon}"}
        client = get_http_client()
        try:
            resp = await client.get(NWS_ALERTS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "error": f"NWS alerts API unreachable: {exc}",
            }

        out = []
        for feature in data.get("features", []) or []:
            p = feature.get("properties") or {}
            event = p.get("event")
            if event not in RELEVANT_EVENTS:
                continue
            out.append({
                "event": event,
                "severity": p.get("severity"),
                "headline": p.get("headline"),
                "description": (p.get("description") or "").strip()[:600],
                "instruction": (p.get("instruction") or "").strip()[:400] or None,
                "effective": p.get("effective"),
                "ends": p.get("ends") or p.get("expires"),
                "sender": p.get("senderName"),
            })

        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "count": len(out),
            "alerts": out,
            "all_clear": len(out) == 0,
        }

    return await get_cache().get_or_set(f"alerts:{beach.slug}", fetch)
