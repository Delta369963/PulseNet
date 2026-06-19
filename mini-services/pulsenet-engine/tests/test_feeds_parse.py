"""Unit tests for feed parsing (geo + RSS + USGS) using fixtures, no network."""

import httpx
import pytest

from app.feeds.geo import haversine_km, nearest_countries
from app.feeds.rss import RssFeed
from app.feeds.usgs import UsgsFeed, mag_severity

COUNTRIES = [
    {"code": "RUS", "lat": 61.5, "lng": 105.3},
    {"code": "UKR", "lat": 48.4, "lng": 31.2},
    {"code": "JPN", "lat": 36.2, "lng": 138.3},
]


def test_haversine_known_distance():
    # Kyiv (UKR) to Moscow-ish region — should be < 1000 km.
    d = haversine_km(50.45, 30.52, 55.75, 37.62)
    assert 600 < d < 900


def test_nearest_countries_within_radius():
    # A point near Ukraine should match UKR first.
    codes = nearest_countries(49.0, 32.0, COUNTRIES, max_km=1500, limit=2)
    assert codes[0] == "UKR"


def test_nearest_countries_empty_when_far():
    # Mid-Pacific: nothing within radius.
    assert nearest_countries(0.0, -150.0, COUNTRIES, max_km=1000) == []


def test_mag_severity_thresholds():
    assert mag_severity(7.0) == "severe"
    assert mag_severity(5.8) == "high"
    assert mag_severity(4.6) == "moderate"


@pytest.mark.asyncio
async def test_usgs_parses_geojson():
    geojson = {
        "features": [
            {
                "properties": {"mag": 6.7, "place": "Test Ridge", "time": 0, "url": "u", "title": "t"},
                "geometry": {"coordinates": [51.2, 28.4, 10]},
            },
            {  # below threshold, dropped
                "properties": {"mag": 3.0, "place": "Small", "time": 0, "url": "u", "title": "t"},
                "geometry": {"coordinates": [10, 10, 1]},
            },
        ]
    }

    def handler(request):
        return httpx.Response(200, json=geojson)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        items = await UsgsFeed().fetch(client)
    assert len(items) == 1
    assert items[0].prestructured is True
    assert items[0].severity == "severe"
    assert items[0].lat == 28.4 and items[0].lng == 51.2


@pytest.mark.asyncio
async def test_rss_parses_entries():
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>Port strike halts grain exports</title>
    <description>A &lt;b&gt;strike&lt;/b&gt; disrupts wheat shipping.</description>
    <link>https://example.com/a</link></item>
    </channel></rss>"""

    def handler(request):
        return httpx.Response(200, content=rss)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        items = await RssFeed("TestRSS", "https://x/rss").fetch(client)
    assert len(items) == 1
    assert "Port strike" in items[0].title
    assert "<b>" not in items[0].summary  # HTML stripped
    assert items[0].prestructured is False
