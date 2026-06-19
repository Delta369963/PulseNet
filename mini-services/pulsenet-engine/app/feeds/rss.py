"""Generic RSS source — GDACS, ReliefWeb, BBC-World, AlJazeera, Google News, and
any regional/news RSS feed.

These are UNSTRUCTURED: title + summary text only. They are handed to the agent
layer (Alpha/Beta) for translation + structured extraction. feedparser handles
RSS/Atom/XML quirks across ~100 country feeds.

Google News RSS (used as a site: proxy for Reuters, AP, etc.) appends
" - SourceName" to the end of titles. We strip that suffix and use the
underlying publisher name as an additional label in the source field.
"""

from __future__ import annotations

import re
import time as _time

import feedparser
import httpx

from app.feeds.base import FeedSource
from app.logging import get_logger
from app.schemas import RawItem

logger = get_logger("feeds.rss")

# Google News appends "- Publisher Name" at the end of every article title
_GNEWS_SUFFIX = re.compile(r"\s+-\s+[\w\s\.&']{2,40}$")

# Known colour prefixes from GDACS alert levels
_GDACS_COLOURS = ("Green ", "Orange ", "Red ")


def _hours_ago(struct_time) -> float:
    if not struct_time:
        return 12.0
    try:
        published = _time.mktime(struct_time)
        return max(0.0, round((_time.time() - published) / 3600, 1))
    except Exception:  # noqa: BLE001
        return 12.0


def _clean_title(title: str, is_gnews: bool) -> tuple[str, str | None]:
    """Strip GDACS colour prefixes and Google News publisher suffixes.

    Returns (cleaned_title, publisher_suffix | None).
    """
    for colour in _GDACS_COLOURS:
        if title.startswith(colour):
            title = title[len(colour):]
            title = title[0].upper() + title[1:] if title else ""
            break

    publisher = None
    if is_gnews:
        m = _GNEWS_SUFFIX.search(title)
        if m:
            publisher = m.group(0).strip(" -").strip()
            title = title[: m.start()].strip()

    return title, publisher


class RssFeed(FeedSource):
    """One configured RSS endpoint. `name` is the source label, `lang` the locale."""

    def __init__(self, name: str, url: str, lang: str = "en", max_items: int = 20):
        self.name = name
        self.url = url
        self.lang = lang
        self.max_items = max_items
        # Detect if this is a Google News aggregator feed
        self._is_gnews = "news.google.com" in url

    async def fetch(self, client: httpx.AsyncClient) -> list[RawItem]:
        resp = await self._get(client, self.url)
        if resp is None:
            return []
        parsed = feedparser.parse(resp.content)
        items: list[RawItem] = []
        for entry in parsed.entries[: self.max_items]:
            raw_title = getattr(entry, "title", "").strip()
            if not raw_title:
                continue

            title, publisher = _clean_title(raw_title, self._is_gnews)
            if not title:
                continue

            # For GNews feeds, label as e.g. "GNews-Reuters[Reuters]" so the LLM
            # knows the original publisher and can use it in the source field.
            source_label = self.name
            if publisher:
                source_label = f"{self.name}[{publisher}]"

            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            source_url = getattr(entry, "link", None)

            items.append(
                RawItem(
                    source=source_label,
                    source_url=source_url,
                    title=title,
                    summary=_strip_html(summary)[:600],
                    lang=self.lang,
                    published_hours_ago=_hours_ago(getattr(entry, "published_parsed", None)),
                    prestructured=False,
                )
            )

        logger.info(
            "rss_feed_fetched",
            extra={"extra": {"feed": self.name, "items": len(items), "total_in_feed": len(parsed.entries)}},
        )
        return items


def _strip_html(text: str) -> str:
    """Cheap HTML tag stripper (RSS summaries often contain markup)."""
    return re.sub(r"<[^>]+>", " ", text or "").replace("&nbsp;", " ").strip()
