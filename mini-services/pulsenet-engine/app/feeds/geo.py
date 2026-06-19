"""Geo helpers — Haversine distance + nearest-country matching.

Mirrors src/lib/pulsenet/geo.ts so Python ingestion tags the same countries the
TS code would. Pure functions, no I/O.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_countries(
    lat: float,
    lng: float,
    countries: list[dict],
    max_km: float = 1500.0,
    limit: int = 3,
) -> list[str]:
    """Return ISO codes of the nearest catalog countries within max_km.

    Args:
        countries: list of dicts with keys code, lat, lng.
    """
    scored = []
    for c in countries:
        d = haversine_km(lat, lng, c["lat"], c["lng"])
        if d <= max_km:
            scored.append((d, c["code"]))
    scored.sort(key=lambda x: x[0])
    return [code for _, code in scored[:limit]]
