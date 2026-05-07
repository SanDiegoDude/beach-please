"""Beach data tools — each one is exposed both as a REST helper and as an LLM tool.

The agent uses TOOL_SCHEMAS for OpenAI tool-calling. TOOL_DISPATCH maps tool
names to the actual async functions so the agent can execute calls.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.tools import (
    alerts,
    amenities,
    rip_currents,
    sharks,
    tides,
    water_quality,
    waves,
)


def _beach_arg() -> dict[str, Any]:
    return {
        "type": "string",
        "description": "Beach slug from the catalog (e.g. 'huntington-beach-ca'). Use lookup_beach if unsure.",
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_beach",
            "description": (
                "Find a US beach by name. First checks the curated catalog, then falls back to "
                "live OpenStreetMap geocoding so ANY US beach name works. Returns matches with slugs "
                "you can pass to other tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Beach name and optionally state, e.g. 'Cocoa Beach FL', 'Pismo', "
                            "'Stinson Beach'. State helps disambiguate."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_beaches",
            "description": (
                "List the curated catalog of well-known US beaches. Use this when the user is browsing "
                "or hasn't named a specific beach. (You can also ask about beaches NOT in this list \u2014 "
                "lookup_beach will geocode any US beach live.)"
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_waves",
            "description": "Current wave height (ft), period (s), and swell direction for a beach. Source: Open-Meteo Marine.",
            "parameters": {
                "type": "object",
                "properties": {"beach_slug": _beach_arg()},
                "required": ["beach_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rip_current_risk",
            "description": "Today's rip current risk forecast (Low/Moderate/High) for a beach. Source: NOAA NWS.",
            "parameters": {
                "type": "object",
                "properties": {"beach_slug": _beach_arg()},
                "required": ["beach_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_alerts",
            "description": "Active NWS alerts (Beach Hazards, Rip Current, High Surf, Tropical) for a beach's location.",
            "parameters": {
                "type": "object",
                "properties": {"beach_slug": _beach_arg()},
                "required": ["beach_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tides",
            "description": "Next high/low tide predictions and current water temperature (F) for a beach.",
            "parameters": {
                "type": "object",
                "properties": {"beach_slug": _beach_arg()},
                "required": ["beach_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_water_quality",
            "description": (
                "Live water quality / bacterial advisory / closure status for a beach. "
                "Real-time coverage: San Diego County CA (sdbeachinfo.com — includes "
                "Tijuana sewage closures at Imperial Beach / Border Field) and "
                "Florida DOH Healthy Beaches. Other states: returns a graceful "
                "fallback link to the right portal."
            ),
            "parameters": {
                "type": "object",
                "properties": {"beach_slug": _beach_arg()},
                "required": ["beach_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shark_history",
            "description": "Historical shark incident counts within a radius around a beach. Source: GSAF dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beach_slug": _beach_arg(),
                    "radius_miles": {
                        "type": "number",
                        "description": "Search radius in miles. Defaults to 50.",
                    },
                },
                "required": ["beach_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_amenities",
            "description": "Toilets, showers, parking, and lifeguard towers near a beach. Source: OpenStreetMap.",
            "parameters": {
                "type": "object",
                "properties": {"beach_slug": _beach_arg()},
                "required": ["beach_slug"],
            },
        },
    },
]


async def _lookup_beach(query: str) -> dict[str, Any]:
    from app.catalog import add_dynamic, find_by_name
    from app.geocoding import geocode_beach

    matches = find_by_name(query)
    if matches:
        return {
            "query": query,
            "count": len(matches),
            "source": "catalog",
            "matches": [m.model_dump() for m in matches[:10]],
        }

    geocoded = await geocode_beach(query)
    if geocoded is None:
        return {
            "query": query,
            "count": 0,
            "source": "geocoder",
            "matches": [],
            "note": (
                f"Could not geocode '{query}' as a US beach. Try adding the state "
                "(e.g. 'Pismo Beach CA') or pick from list_beaches."
            ),
        }

    saved = add_dynamic(geocoded)
    return {
        "query": query,
        "count": 1,
        "source": "live-geocoded",
        "note": (
            "Not in the curated catalog. Added live via OpenStreetMap. "
            "Use the slug below with the data tools just like a catalog beach."
        ),
        "matches": [saved.model_dump()],
    }


async def _list_beaches() -> dict[str, Any]:
    from app.catalog import load_catalog

    items = load_catalog()
    return {
        "count": len(items),
        "beaches": [
            {"slug": b.slug, "name": b.name, "state": b.state, "region": b.region}
            for b in items
        ],
    }


TOOL_DISPATCH: dict[str, Callable[..., Awaitable[Any]]] = {
    "lookup_beach": _lookup_beach,
    "list_beaches": _list_beaches,
    "get_waves": waves.get_waves,
    "get_rip_current_risk": rip_currents.get_rip_current_risk,
    "get_active_alerts": alerts.get_active_alerts,
    "get_tides": tides.get_tides,
    "get_water_quality": water_quality.get_water_quality,
    "get_shark_history": sharks.get_shark_history,
    "get_amenities": amenities.get_amenities,
}
