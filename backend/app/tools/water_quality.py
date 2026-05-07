"""Water quality / bacterial advisory status.

National coverage is fragmented. We use:
- San Diego County (CA): sdbeachinfo.com (real-time per-station closures,
  including the Tijuana sewage flow situation that closes Imperial Beach
  for months at a time).
- Florida: FL DOH Healthy Beaches ArcGIS FeatureServer.
- Elsewhere: degrade gracefully and point users at the right state portal.
"""
from __future__ import annotations

import html as html_lib
import math
import re
from typing import Any

from app.cache import get_cache
from app.catalog import get_by_slug
from app.http import get_http_client

FL_DOH_URL = (
    "https://services1.arcgis.com/CY1LXxl9zlJeBuRZ/ArcGIS/rest/services/"
    "Florida_Healthy_Beaches/FeatureServer/0/query"
)

SD_TARGETS_URL = "https://www.sdbeachinfo.com/Home/GetTargetByID"

# San Diego County DEH covers from the Mexican border up to Trestles. Anything
# south of ~33.5N within ~30km of the coast falls in their service area.
SD_LAT_MIN, SD_LAT_MAX = 32.50, 33.55
SD_LON_MIN, SD_LON_MAX = -117.65, -117.10

# Status icons returned by sdbeachinfo. We collapse to a clean enum.
SD_STATUS_MAP = {
    "Red.png": ("closure", "CLOSURE \u2014 do not enter the water"),
    "Yellow.png": ("advisory", "Advisory \u2014 elevated bacteria, swim with caution"),
    "Green.png": ("clear", "No advisories or closures"),
    "Outfall.png": ("outfall", "Outfall monitoring station (informational only)"),
}

_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    text = _HTML_TAG.sub(" ", s)
    text = html_lib.unescape(text).replace("\u00a0", " ")
    return _WS.sub(" ", text).strip()


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Crude great-circle distance for nearest-station selection."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


async def _fetch_sd_county(lat: float, lon: float) -> dict[str, Any] | None:
    """Pull San Diego County DEH live monitoring stations.

    Returns the nearest in-area station's status, plus the worst status across
    everything within 5 km (so a beach near Imperial gets the closure flag
    even if its primary station isn't the one in active alarm).
    """
    cache = get_cache()

    async def fetch_targets() -> list[dict[str, Any]]:
        client = get_http_client()
        resp = await client.get(SD_TARGETS_URL, timeout=12)
        resp.raise_for_status()
        return resp.json()

    targets = await cache.get_or_set("sd-county-water-targets", fetch_targets)
    if not targets:
        return None

    scored: list[tuple[float, dict[str, Any]]] = []
    for t in targets:
        try:
            tlat = float(t["Latitude"])
            tlon = float(t["Longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        d = _km(lat, lon, tlat, tlon)
        scored.append((d, t))
    scored.sort(key=lambda x: x[0])
    if not scored or scored[0][0] > 8:
        return None

    nearest_dist, nearest = scored[0]
    nearby = [(d, t) for d, t in scored if d <= 5.0]

    def classify(t: dict[str, Any]) -> str:
        icon = (t.get("RBGColor") or "").strip()
        return SD_STATUS_MAP.get(icon, ("unknown", icon))[0]

    severity_order = {"closure": 3, "advisory": 2, "outfall": 1, "clear": 0, "unknown": 0}
    worst = max(nearby, key=lambda dt: severity_order.get(classify(dt[1]), 0)) if nearby else (nearest_dist, nearest)
    worst_dist, worst_t = worst
    worst_status = classify(worst_t)
    worst_label = SD_STATUS_MAP.get((worst_t.get("RBGColor") or "").strip(), ("unknown", "Unknown"))[1]

    advisory_text = _strip_html(worst_t.get("Advisory") or worst_t.get("Closure") or "")
    general_msg = _strip_html(worst_t.get("GeneralAdvisoryMessage") or "")

    closures_in_5km = sum(1 for d, t in nearby if classify(t) == "closure")
    advisories_in_5km = sum(1 for d, t in nearby if classify(t) == "advisory")

    return {
        "status": worst_status,
        "status_label": worst_label,
        "status_text": advisory_text or general_msg or None,
        "station": worst_t.get("Name"),
        "station_id": worst_t.get("DehID"),
        "station_distance_km": round(worst_dist, 2),
        "nearby_closures_within_5km": closures_in_5km,
        "nearby_advisories_within_5km": advisories_in_5km,
        "stations_checked": len(nearby) or 1,
        "source": "San Diego County DEH (sdbeachinfo.com)",
        "external_url": "https://www.sdbeachinfo.com/",
    }


async def _fetch_florida(lat: float, lon: float) -> dict[str, Any] | None:
    params = {
        "where": "1=1",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "distance": "5",
        "units": "esriSRUnit_StatuteMile",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "orderByFields": "SAMPLEDATE DESC",
        "resultRecordCount": "1",
        "f": "json",
    }
    client = get_http_client()
    try:
        resp = await client.get(FL_DOH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    feats = data.get("features") or []
    if not feats:
        return None
    a = feats[0].get("attributes") or {}
    return {
        "status": a.get("ADVISORY") or a.get("RESULT") or "unknown",
        "sample_date": a.get("SAMPLEDATE"),
        "site": a.get("SITE_NAME") or a.get("BEACH_NAME"),
        "source": "Florida DOH Healthy Beaches",
    }


def _in_sd_county(lat: float, lon: float) -> bool:
    return SD_LAT_MIN <= lat <= SD_LAT_MAX and SD_LON_MIN <= lon <= SD_LON_MAX


async def get_water_quality(beach_slug: str) -> dict[str, Any]:
    beach = get_by_slug(beach_slug)
    if not beach:
        return {"error": f"Unknown beach slug: {beach_slug}"}

    async def fetch() -> dict[str, Any]:
        base = {"beach_slug": beach.slug, "beach_name": beach.name}

        if beach.state == "FL":
            res = await _fetch_florida(beach.lat, beach.lon)
            if res:
                return {**base, "available": True, **res}
            return {
                **base,
                "available": False,
                "note": (
                    "No recent FL DOH Healthy Beaches sample within 5 miles. "
                    "Probably means no advisories \u2014 still, check posted signs."
                ),
                "external_url": "https://www.floridahealth.gov/environmental-health/beach-water-quality/",
            }

        if beach.state == "CA" and _in_sd_county(beach.lat, beach.lon):
            try:
                sd = await _fetch_sd_county(beach.lat, beach.lon)
            except Exception as exc:
                sd = None
                base["fetch_error"] = str(exc)
            if sd:
                return {**base, "available": True, **sd}
            return {
                **base,
                "available": False,
                "note": (
                    "No San Diego County DEH monitoring station within 8 km of this beach."
                ),
                "external_url": "https://www.sdbeachinfo.com/",
            }

        if beach.state == "CA":
            return {
                **base,
                "available": False,
                "note": (
                    "California beach grades for this region come from the Heal the "
                    "Bay Beach Report Card (no public API). Check the link below."
                ),
                "external_url": (
                    f"https://beachreportcard.org/search?query={beach.name.replace(' ', '+')}"
                ),
            }

        return {
            **base,
            "available": False,
            "note": (
                f"No structured real-time water quality feed wired up for {beach.state}. "
                "Try EPA BEACON or your state's beach program."
            ),
            "external_url": "https://watersgeo.epa.gov/beacon2/",
        }

    return await get_cache().get_or_set(f"wq:{beach.slug}", fetch)
