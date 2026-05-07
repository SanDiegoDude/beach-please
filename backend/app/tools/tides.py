"""Tides and water temperature from NOAA CO-OPS API.

Catalog beaches usually have a pre-mapped tide station. Live-geocoded beaches
don't, so we lazily fetch the full CO-OPS station list once and find the
closest tide-prediction station to a given lat/lon.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug, haversine_miles
from app.http import get_http_client

CO_OPS_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
CO_OPS_STATIONS_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
)


_station_cache: list[dict[str, Any]] | None = None


async def _load_stations() -> list[dict[str, Any]]:
    global _station_cache
    if _station_cache is not None:
        return _station_cache
    client = get_http_client()
    try:
        resp = await client.get(CO_OPS_STATIONS_URL, params={"type": "tidepredictions"})
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    out = []
    for s in data.get("stations", []) or []:
        try:
            out.append({"id": s["id"], "name": s["name"], "lat": float(s["lat"]), "lon": float(s["lng"])})
        except (KeyError, ValueError):
            continue
    _station_cache = out
    return out


async def find_nearest_station(lat: float, lon: float, max_miles: float = 40.0) -> str | None:
    stations = await _load_stations()
    if not stations:
        return None
    best: tuple[float, str] | None = None
    for s in stations:
        d = haversine_miles(lat, lon, s["lat"], s["lon"])
        if best is None or d < best[0]:
            best = (d, s["id"])
    if best and best[0] <= max_miles:
        return best[1]
    return None


def _today_range() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=36)
    fmt = "%Y%m%d %H:%M"
    return now.strftime(fmt), end.strftime(fmt)


async def _fetch_tides(station: str) -> list[dict[str, Any]]:
    begin, end = _today_range()
    params = {
        "product": "predictions",
        "begin_date": begin,
        "end_date": end,
        "datum": "MLLW",
        "station": station,
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
    }
    client = get_http_client()
    try:
        resp = await client.get(CO_OPS_URL, params=params)
        resp.raise_for_status()
        return resp.json().get("predictions", []) or []
    except Exception:
        return []


async def _fetch_water_temp(station: str) -> dict[str, Any] | None:
    params = {
        "product": "water_temperature",
        "date": "latest",
        "station": station,
        "time_zone": "lst_ldt",
        "units": "english",
        "format": "json",
    }
    client = get_http_client()
    try:
        resp = await client.get(CO_OPS_URL, params=params)
        resp.raise_for_status()
        items = resp.json().get("data", []) or []
        if not items:
            return None
        latest = items[-1]
        return {"value_f": float(latest["v"]), "as_of": latest.get("t")}
    except Exception:
        return None


async def get_tides(beach_slug: str) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    station = beach.tide_station
    resolved_dynamically = False
    if not station:
        station = await find_nearest_station(beach.lat, beach.lon)
        resolved_dynamically = station is not None
    if not station:
        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "available": False,
            "note": "No CO-OPS tide station within ~40 miles of this point.",
        }

    async def fetch() -> dict[str, Any]:
        predictions, water_temp = (
            await _fetch_tides(station),
            await _fetch_water_temp(station),
        )
        next_events = [
            {
                "type": "high" if p.get("type") == "H" else "low",
                "time": p.get("t"),
                "height_ft": float(p.get("v", 0)),
            }
            for p in predictions[:6]
        ]
        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "station": station,
            "station_resolved_live": resolved_dynamically,
            "available": bool(next_events),
            "next_events": next_events,
            "water_temperature": water_temp,
        }

    return await get_cache().get_or_set(f"tides:{beach.slug}:{station}", fetch)
