"""Wave/swell conditions from Open-Meteo Marine API.

Gotcha discovered during research: the API silently returns zeros/nulls unless
you (a) pin a model that has data for your area and (b) shift the query point
slightly seaward. We do both.
"""
from __future__ import annotations

import math
from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug
from app.http import get_http_client

OPEN_METEO_URL = "https://marine-api.open-meteo.com/v1/marine"

OFFSHORE_OFFSET_DEG = 0.06


def _candidate_offsets(lat: float, lon: float) -> list[tuple[float, float]]:
    """Return seaward query candidates to try in order.

    The beach's own lat/lon often falls on a land grid cell with no marine
    data. We try cardinals first (most beaches face one of N/S/E/W), then
    diagonals, then the original point. First non-null response wins.

    Order is biased by likely US coast: West coast prefers W, Gulf prefers W,
    Atlantic prefers E, Hawaii prefers S (open ocean).
    """
    d = OFFSHORE_OFFSET_DEG
    if lon < -150:
        priority = [(-d, 0), (0, -d), (0, d), (d, 0)]
    elif lon < -120:
        priority = [(0, -d), (-d, 0), (d, 0), (0, d)]
    elif -97 < lon < -80 and lat < 31:
        priority = [(0, -d), (0, d), (-d, 0), (d, 0)]
    else:
        priority = [(0, d), (-d, 0), (d, 0), (0, -d)]
    diagonals = [(d, d), (d, -d), (-d, d), (-d, -d)]
    return [(lat + dlat, lon + dlon) for dlat, dlon in priority + diagonals] + [(lat, lon)]


def _meters_to_feet(m: float | None) -> float | None:
    if m is None:
        return None
    return round(m * 3.28084, 1)


def _deg_to_compass(deg: float | None) -> str | None:
    if deg is None:
        return None
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((deg + 11.25) // 22.5) % 16
    return dirs[idx]


async def get_waves(beach_slug: str) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    async def fetch() -> dict[str, Any]:
        client = get_http_client()
        data: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for lat, lon in _candidate_offsets(beach.lat, beach.lon):
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "wave_height,wave_period,wave_direction,swell_wave_height,swell_wave_period,swell_wave_direction,wind_wave_height",
                "length_unit": "metric",
                "timezone": "auto",
                "models": "ncep_gfswave025",
            }
            try:
                resp = await client.get(OPEN_METEO_URL, params=params)
                resp.raise_for_status()
                attempt = resp.json()
            except Exception as exc:
                last_exc = exc
                continue
            current = attempt.get("current", {}) or {}
            if current.get("wave_height") is not None:
                data = attempt
                break

        if data is None:
            if last_exc is not None:
                return {
                    "beach_slug": beach.slug,
                    "beach_name": beach.name,
                    "error": f"Open-Meteo Marine unreachable: {last_exc}",
                }
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "available": False,
                "note": "No marine grid coverage near this beach.",
            }

        current = data.get("current", {}) or {}

        wave_h_ft = _meters_to_feet(current.get("wave_height"))
        swell_h_ft = _meters_to_feet(current.get("swell_wave_height"))
        wind_wave_ft = _meters_to_feet(current.get("wind_wave_height"))

        if wave_h_ft is None or (wave_h_ft == 0 and swell_h_ft in (None, 0)):
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "available": False,
                "note": "No marine grid coverage at this exact point. Open-Meteo can't see this beach.",
            }

        size_label = _label_wave_size(wave_h_ft)

        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "available": True,
            "as_of": current.get("time"),
            "timezone": data.get("timezone"),
            "wave_height_ft": wave_h_ft,
            "wave_period_s": current.get("wave_period"),
            "wave_direction": _deg_to_compass(current.get("wave_direction")),
            "swell_height_ft": swell_h_ft,
            "swell_period_s": current.get("swell_wave_period"),
            "swell_direction": _deg_to_compass(current.get("swell_wave_direction")),
            "wind_wave_height_ft": wind_wave_ft,
            "size_label": size_label,
        }

    return await get_cache().get_or_set(f"waves:{beach.slug}", fetch)


def _label_wave_size(ft: float | None) -> str:
    if ft is None:
        return "unknown"
    if ft < 1:
        return "flat"
    if ft < 2:
        return "ankle-to-knee"
    if ft < 3:
        return "knee-to-waist"
    if ft < 5:
        return "waist-to-shoulder"
    if ft < 8:
        return "head-high-plus"
    if ft < 12:
        return "overhead, expert only"
    return "huge, do not enter"
