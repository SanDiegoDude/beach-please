"""Beach catalog: pre-baked metadata so we don't hammer Nominatim at runtime."""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DATA_DIR = Path(__file__).parent / "data"
CATALOG_PATH = DATA_DIR / "beaches.json"


class Beach(BaseModel):
    slug: str
    name: str
    state: str
    region: str
    lat: float
    lon: float
    nws_zone: str | None = None
    tide_station: str | None = None
    description: str | None = None
    tags: list[str] = []


_dynamic: dict[str, Beach] = {}


@lru_cache(maxsize=1)
def _load_static_catalog() -> list[Beach]:
    raw = json.loads(CATALOG_PATH.read_text())
    return [Beach(**item) for item in raw]


def load_catalog() -> list[Beach]:
    """Static catalog plus any beaches added live at runtime via geocoding."""
    return list(_load_static_catalog()) + list(_dynamic.values())


def add_dynamic(beach: Beach) -> Beach:
    """Add a runtime-geocoded beach to the in-memory catalog. Idempotent.

    If a slug collision exists, suffix with -1, -2, ... so the new entry
    is reachable without overwriting whatever was there.
    """
    if get_by_slug(beach.slug):
        existing = get_by_slug(beach.slug)
        if existing and abs(existing.lat - beach.lat) < 0.01 and abs(existing.lon - beach.lon) < 0.01:
            return existing
        i = 1
        while get_by_slug(f"{beach.slug}-{i}"):
            i += 1
        beach = beach.model_copy(update={"slug": f"{beach.slug}-{i}"})
    _dynamic[beach.slug] = beach
    return beach


def get_by_slug(slug: str) -> Beach | None:
    slug_clean = slug.strip().lower()
    if slug_clean in _dynamic:
        return _dynamic[slug_clean]
    for beach in _load_static_catalog():
        if beach.slug == slug_clean:
            return beach
    return None


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def find_by_name(query: str) -> list[Beach]:
    """Case-insensitive substring search across name + state."""
    q = query.lower().strip()
    if not q:
        return []
    results: list[tuple[int, Beach]] = []
    for beach in load_catalog():
        haystack = f"{beach.name} {beach.state} {beach.region}".lower()
        if q in haystack:
            score = 0 if beach.name.lower().startswith(q) else 1
            results.append((score, beach))
    results.sort(key=lambda r: (r[0], r[1].name))
    return [b for _, b in results]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def find_near(lat: float, lon: float, radius_miles: float = 50.0) -> list[Beach]:
    results = []
    for beach in load_catalog():
        d = haversine_miles(lat, lon, beach.lat, beach.lon)
        if d <= radius_miles:
            results.append((d, beach))
    results.sort(key=lambda r: r[0])
    return [b for _, b in results]
