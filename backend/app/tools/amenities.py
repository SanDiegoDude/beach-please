"""Beach amenities (toilets, showers, parking, lifeguards) via OSM Overpass API."""
from __future__ import annotations

from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug
from app.http import get_http_client

OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
RADIUS_METERS = 600


def _build_query(lat: float, lon: float, radius: int) -> str:
    return f"""
[out:json][timeout:15];
(
  node["amenity"="toilets"](around:{radius},{lat},{lon});
  node["amenity"="shower"](around:{radius},{lat},{lon});
  node["amenity"="parking"](around:{radius},{lat},{lon});
  way["amenity"="parking"](around:{radius},{lat},{lon});
  node["emergency"="lifeguard_tower"](around:{radius},{lat},{lon});
  node["leisure"="lifeguard_tower"](around:{radius},{lat},{lon});
  node["amenity"="bbq"](around:{radius},{lat},{lon});
  node["amenity"="drinking_water"](around:{radius},{lat},{lon});
);
out center tags;
""".strip()


_CATEGORY_MAP = {
    ("amenity", "toilets"): "toilets",
    ("amenity", "shower"): "showers",
    ("amenity", "parking"): "parking",
    ("amenity", "bbq"): "bbq",
    ("amenity", "drinking_water"): "drinking_water",
    ("emergency", "lifeguard_tower"): "lifeguard_towers",
    ("leisure", "lifeguard_tower"): "lifeguard_towers",
}


async def get_amenities(beach_slug: str) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    async def fetch() -> dict[str, Any]:
        query = _build_query(beach.lat, beach.lon, RADIUS_METERS)
        client = get_http_client()
        last_exc: Exception | None = None
        data = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                resp = await client.post(endpoint, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                last_exc = exc
                continue
        if data is None:
            return {
                "beach_slug": beach.slug,
                "beach_name": beach.name,
                "error": f"All Overpass mirrors failed: {last_exc}",
            }

        counts: dict[str, int] = {label: 0 for label in set(_CATEGORY_MAP.values())}
        examples: dict[str, list[str]] = {label: [] for label in counts}

        for elem in data.get("elements", []):
            tags = elem.get("tags", {}) or {}
            for (k, v), label in _CATEGORY_MAP.items():
                if tags.get(k) == v:
                    counts[label] += 1
                    name = tags.get("name") or tags.get("operator")
                    if name and len(examples[label]) < 3:
                        examples[label].append(name)
                    break

        return {
            "beach_slug": beach.slug,
            "beach_name": beach.name,
            "available": True,
            "search_radius_m": RADIUS_METERS,
            "counts": counts,
            "examples": {k: v for k, v in examples.items() if v},
            "summary": _summarize(counts),
        }

    return await get_cache().get_or_set(f"amenities:{beach.slug}", fetch)


def _summarize(counts: dict[str, int]) -> str:
    have = [k.replace("_", " ") for k, v in counts.items() if v > 0]
    if not have:
        return "No mapped amenities nearby. Pack accordingly."
    return "Has: " + ", ".join(sorted(have)) + "."
