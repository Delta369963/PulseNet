"""Feed registry — loads feeds.yaml and runs all enabled sources concurrently.

One dead feed never breaks the run: each source is gathered with
return_exceptions=True and failures are logged, not raised.
"""

from __future__ import annotations

import asyncio

import httpx
import yaml

from app.config import get_settings
from app.feeds.acled import AcledFeed
from app.feeds.base import FeedSource
from app.feeds.rss import RssFeed
from app.feeds.usgs import UsgsFeed
from app.logging import get_logger
from app.schemas import RawItem


logger = get_logger("feeds.registry")


def load_sources(config_path: str | None = None) -> list[FeedSource]:
    """Build the list of enabled FeedSource objects from feeds.yaml."""
    settings = get_settings()
    path = config_path or settings.feeds_config_path
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    sources: list[FeedSource] = []

    if (cfg.get("usgs") or {}).get("enabled", True):
        sources.append(UsgsFeed())

    for entry in cfg.get("rss", []) or []:
        if not entry.get("enabled", False):
            continue
        sources.append(
            RssFeed(
                name=entry["name"],
                url=entry["url"],
                lang=entry.get("lang", "en"),
                max_items=entry.get("max_items", 20),
            )
        )

    # ACLED: conditionally add based on token presence.
    acled = AcledFeed()
    if acled.enabled:
        sources.append(acled)

    logger.info(
        "feed sources loaded",
        extra={"extra": {"count": len(sources), "names": [s.name for s in sources]}},
    )
    return sources



async def fetch_all(sources: list[FeedSource]) -> list[RawItem]:
    """Fetch all sources concurrently, isolating per-source failures."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(src.fetch(client) for src in sources),
            return_exceptions=True,
        )

    items: list[RawItem] = []
    for src, res in zip(sources, results, strict=True):
        if isinstance(res, Exception):
            logger.warning(
                "source raised during fetch",
                extra={"extra": {"source": src.name, "err": str(res)}},
            )
            continue
        items.extend(res)
    return items
