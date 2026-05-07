"""Beach catalog and aggregated report endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.agent import generate_blurb
from app.catalog import find_by_name, get_by_slug, load_catalog
from app.tools import alerts, amenities, rip_currents, sharks, tides, water_quality, waves

router = APIRouter()


@router.get("/beaches")
async def list_beaches(q: str | None = Query(default=None)) -> dict[str, Any]:
    if q:
        items = find_by_name(q)
    else:
        items = load_catalog()
    return {
        "count": len(items),
        "beaches": [b.model_dump() for b in items],
    }


@router.get("/beaches/{slug}")
async def get_beach(slug: str) -> dict[str, Any]:
    beach = get_by_slug(slug)
    if not beach:
        raise HTTPException(status_code=404, detail=f"No beach with slug '{slug}'")
    return beach.model_dump()


@router.get("/beaches/{slug}/report")
async def beach_report(slug: str, blurb: bool = True) -> dict[str, Any]:
    """Fan out every data tool in parallel and stitch results into one card."""
    beach = get_by_slug(slug)
    if not beach:
        raise HTTPException(status_code=404, detail=f"No beach with slug '{slug}'")

    waves_d, rip_d, alerts_d, tides_d, wq_d, sharks_d, amen_d = await asyncio.gather(
        waves.get_waves(slug),
        rip_currents.get_rip_current_risk(slug),
        alerts.get_active_alerts(slug),
        tides.get_tides(slug),
        water_quality.get_water_quality(slug),
        sharks.get_shark_history(slug),
        amenities.get_amenities(slug),
    )

    report: dict[str, Any] = {
        "beach": beach.model_dump(),
        "waves": waves_d,
        "rip_currents": rip_d,
        "alerts": alerts_d,
        "tides": tides_d,
        "water_quality": wq_d,
        "sharks": sharks_d,
        "amenities": amen_d,
    }

    if blurb:
        report["blurb"] = await generate_blurb(report)

    return report
