"""USGS earthquakes — structured GeoJSON feed (keyless, public).

Pre-structured: USGS gives us magnitude + coords directly, so no LLM is needed.
We mark these RawItems prestructured=True so the agent layer skips them.
"""

from __future__ import annotations

import httpx

from app.feeds.base import FeedSource
from app.schemas import RawItem

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
MIN_MAG = 5.5  # Only ingest significant earthquakes
MAX_EVENTS = 4


def mag_severity(mag: float) -> str:
    if mag >= 6.5:
        return "severe"
    if mag >= 5.5:
        return "high"
    return "moderate"


class UsgsFeed(FeedSource):
    name = "USGS"

    def __init__(self, url: str = USGS_URL, min_mag: float = MIN_MAG, max_events: int = MAX_EVENTS):
        self.url = url
        self.min_mag = min_mag
        self.max_events = max_events

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        resp = await self._get(client, self.url)
        if resp is None:
            return []
        data = resp.json()
        feats = [
            f
            for f in data.get("features", [])
            if (f.get("properties", {}).get("mag") or 0) >= self.min_mag
            and f.get("geometry", {}).get("coordinates")
        ]
        feats.sort(key=lambda f: f["properties"].get("mag", 0), reverse=True)
        items: list[RawItem] = []
        for f in feats[: self.max_events]:
            props = f["properties"]
            lng, lat, *_ = f["geometry"]["coordinates"]
            mag = float(props.get("mag", 0))
            place = props.get("place") or "unknown location"
            time_ms = props.get("time", 0)
            items.append(
                RawItem(
                    source="USGS",
                    source_url=props.get("url") or "https://earthquake.usgs.gov/",
                    title=f"M {mag:.1f} earthquake — {place}",
                    summary=(
                        f"Seismic event detected by USGS (magnitude {mag:.1f}). Potential "
                        "disruption to nearby export terminals, refineries, or transport "
                        "corridors if located near industrialized coastline."
                    ),
                    lat=lat,
                    lng=lng,
                    prestructured=True,
                    severity=mag_severity(mag),
                    shock_type="earthquake",
                    published_hours_ago=_hours_ago_from_ms(time_ms),
                )
            )
        return items


def _hours_ago_from_ms(time_ms: float) -> float:
    import time

    if not time_ms:
        return 1.0
    delta_h = (time.time() * 1000 - time_ms) / 3_600_000
    return max(0.0, round(delta_h, 1))
