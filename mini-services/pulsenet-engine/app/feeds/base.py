"""FeedSource abstraction — every connector implements fetch() -> list[RawItem].

A source that raises is caught by the registry and logged; it never aborts the
whole ingestion run (one dead feed != total failure).
"""

from __future__ import annotations

import abc

import httpx

from app.logging import get_logger
from app.schemas import RawItem

logger = get_logger("feeds")

DEFAULT_TIMEOUT = 12.0
USER_AGENT = "PulseNet/0.1 (civic-infrastructure; decision-support)"


class FeedSource(abc.ABC):
    """Base class for all feed connectors."""

    #: short identifier stored on each shock (USGS, GDACS, ReliefWeb, ...)
    name: str = "base"
    #: whether this source needs a key it does not have (=> skipped)
    enabled: bool = True

    @abc.abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        """Fetch + normalize items. Must not raise on network errors."""
        raise NotImplementedError

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response | None:
        """GET with shared headers; returns None on any failure (logged)."""
        try:
            resp = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp
        except Exception as err:  # noqa: BLE001 — isolate per-source failure
            logger.warning(
                "feed fetch failed",
                extra={"extra": {"source": self.name, "url": url, "err": str(err)}},
            )
            return None
