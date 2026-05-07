"""Shark incident history.

Loads a bundled GSAF-derived CSV of US shark incidents and returns counts
within a radius of a beach. The dataset shipped with the repo is a curated
subset; replace `gsaf_sharks.csv` with the full Kaggle export to get richer
data without code changes.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug, haversine_miles

DATA_PATH = Path(__file__).parent.parent / "data" / "gsaf_sharks.csv"


@lru_cache(maxsize=1)
def _load_incidents() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    out = []
    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                out.append({
                    "year": int(row["year"]),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "location": row.get("location", ""),
                    "activity": row.get("activity", ""),
                    "fatal": row.get("fatal", "").strip().upper() == "Y",
                    "species": row.get("species", ""),
                })
            except (ValueError, KeyError):
                continue
    return out


async def get_shark_history(beach_slug: str, radius_miles: float = 50.0) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    async def fetch() -> dict[str, Any]:
        incidents = _load_incidents()
        if not incidents:
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "available": False,
                "note": "No shark dataset bundled. Drop a GSAF CSV at app/data/gsaf_sharks.csv.",
            }

        nearby = []
        for inc in incidents:
            d = haversine_miles(beach.lat, beach.lon, inc["lat"], inc["lon"])
            if d <= radius_miles:
                nearby.append({**inc, "distance_miles": round(d, 1)})

        nearby.sort(key=lambda r: -r["year"])
        fatal_count = sum(1 for r in nearby if r["fatal"])

        recent = [r for r in nearby if r["year"] >= 2010]

        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "available": True,
            "radius_miles": radius_miles,
            "total_recorded_incidents": len(nearby),
            "fatal_incidents": fatal_count,
            "incidents_since_2010": len(recent),
            "most_recent": nearby[:5],
            "risk_label": _label_risk(len(nearby), fatal_count),
        }

    return await get_cache().get_or_set(f"sharks:{beach.slug}:{radius_miles}", fetch)


def _label_risk(total: int, fatal: int) -> str:
    if fatal >= 3 or total >= 25:
        return "elevated history"
    if total >= 10:
        return "documented history"
    if total > 0:
        return "rare incidents"
    return "no recorded incidents in dataset"
