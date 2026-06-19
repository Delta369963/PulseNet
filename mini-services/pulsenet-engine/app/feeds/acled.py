"""ACLED (Armed Conflict Location & Event Data) feed — OAuth bearer auth.

Fetches the last 14 days of conflict events near major trade infrastructure.
Uses the ACLED OAuth access token from config; auto-refreshes on 401.
Supply-chain relevant event types: Battles, Explosions, Riots, Strategic developments.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


import httpx

from app.config import get_settings
from app.feeds.base import FeedSource
from app.logging import get_logger
from app.schemas import RawItem

logger = get_logger("feeds.acled")

ACLED_API = "https://api.acleddata.com/acled/read"
ACLED_OAUTH = "https://acleddata.com/oauth/token"

# Event types relevant to supply-chain disruption.
RELEVANT_TYPES = {
    "battles", "explosions/remote violence",
    "riots", "strategic developments", "protests",
}

# Simple name → ISO3 mapping for ACLED's "country" field.
_NAME_TO_ISO3: dict[str, str] = {
    "russia": "RUS", "ukraine": "UKR", "india": "IND", "pakistan": "PAK",
    "bangladesh": "BGD", "saudi arabia": "SAU", "united arab emirates": "ARE",
    "qatar": "QAT", "iran": "IRN", "egypt": "EGY", "china": "CHN",
    "japan": "JPN", "south korea": "KOR", "united states": "USA",
    "germany": "DEU", "france": "FRA", "kenya": "KEN", "nigeria": "NGA",
    "ethiopia": "ETH", "sri lanka": "LKA",
}


def _iso3(country_name: str) -> str | None:
    return _NAME_TO_ISO3.get(country_name.lower().strip())


class AcledFeed(FeedSource):
    """ACLED conflict-event feed via OAuth Bearer token."""

    name = "ACLED"

    def __init__(self):
        s = get_settings()
        self._token = s.acled_access_token
        self._refresh = s.acled_refresh_token
        self.enabled = bool(self._token)

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        if not self._token:
            return []
        items = await self._fetch_with_token(client)
        if items is None:
            # 401 → try refresh
            if await self._do_refresh(client):
                items = await self._fetch_with_token(client) or []
            else:
                items = []
        return items

    async def _fetch_with_token(self, client: httpx.AsyncClient) -> list[RawItem] | None:
        """Returns list on success, None on 401."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=14)
        params = {
            "fields": "event_date,event_type,sub_event_type,country,latitude,longitude,location,fatalities,notes,source",
            "limit": "100",
            "format": "json",
            "event_date_where": "BETWEEN",
            "event_date": f"{start.strftime('%Y-%m-%d')}|{end.strftime('%Y-%m-%d')}",
        }
        try:
            resp = await client.get(
                ACLED_API,
                params=params,
                headers={"Authorization": f"Bearer {self._token}", "User-Agent": "PulseNet/0.1"},
                timeout=15.0,
            )
            if resp.status_code == 401:
                logger.warning("ACLED 401 — token expired, will attempt refresh")
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                logger.warning("ACLED API error", extra={"extra": {"resp": str(data)[:200]}})
                return []
            return self._parse(data.get("data", []))
        except Exception as err:  # noqa: BLE001
            logger.warning("ACLED fetch failed", extra={"extra": {"err": str(err)}})
            return []

    async def _do_refresh(self, client: httpx.AsyncClient) -> bool:
        if not self._refresh:
            return False
        try:
            resp = await client.post(
                ACLED_OAUTH,
                data={"refresh_token": self._refresh, "grant_type": "refresh_token", "client_id": "acled"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            if not resp.is_success:
                logger.warning("ACLED token refresh failed", extra={"extra": {"status": resp.status_code}})
                return False
            payload = resp.json()
            self._token = payload.get("access_token", "")
            self._refresh = payload.get("refresh_token", self._refresh)
            logger.info("ACLED token refreshed successfully")
            return bool(self._token)
        except Exception as err:  # noqa: BLE001
            logger.warning("ACLED token refresh error", extra={"extra": {"err": str(err)}})
            return False

    def _parse(self, rows: list[dict]) -> list[RawItem]:
        items: list[RawItem] = []
        for row in rows:
            etype = (row.get("event_type") or "").lower()
            if not any(t in etype for t in RELEVANT_TYPES):
                continue
            country = row.get("country", "")
            iso3 = _iso3(country)
            try:
                lat = float(row.get("latitude") or 0) or None
                lng = float(row.get("longitude") or 0) or None
            except (ValueError, TypeError):
                lat, lng = None, None
            notes = (row.get("notes") or "").strip()[:400]
            title = f"[ACLED {row.get('event_type')}] {row.get('sub_event_type','')} in {row.get('location',country)}"
            summary = f"{notes} (fatalities: {row.get('fatalities','?')}, source: {row.get('source','')})"
            pub_hours = _hours_since(row.get("event_date", ""))
            items.append(RawItem(
                source="ACLED",
                source_url="https://acleddata.com/",
                title=title.strip(),
                summary=summary.strip(),
                lang="en",
                published_hours_ago=pub_hours,
                lat=lat,
                lng=lng,
                prestructured=False,
                country_codes=[iso3] if iso3 else [],
            ))
        return items


def _hours_since(date_str: str) -> float:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0.0, delta.total_seconds() / 3600)
    except (ValueError, TypeError):
        return 24.0
