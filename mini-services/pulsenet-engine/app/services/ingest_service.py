"""Ingestion service — feeds → consensus → ledger → ShockEvent rows.

Flow (one correlation id per run):
  1. load + fetch all enabled feed sources (RSS-first + USGS).
  2. geo-tag USGS items to nearest catalog countries.
  3. PRE-FILTER: drop items whose sourceUrl already exists in DB → no LLM waste.
  4. run Alpha ∥ Beta → Gamma consensus over remaining items.
  5. write a consensus-ledger row per detected crisis (interpretability).
  6. dedupe by externalId + insert new ShockEvents + audit-trail entries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.agents.graph import run_consensus
from app.agents.llm import build_clients
from app.config import get_settings
from app.db import repo
from app.db.session import session_scope
from app.feeds.geo import nearest_countries
from app.feeds.registry import fetch_all, load_sources
from app.logging import get_logger, new_correlation_id
from app.schemas import ConsensusShock, IngestResponse, RawItem

logger = get_logger("services.ingest")


def _external_id(c: ConsensusShock) -> str:
    import base64

    key = f"{c.shock.title}|{c.shock.location_name}"
    return "web-" + base64.b64encode(key.encode()).decode()[:18]


def _geotag_usgs(items: list[RawItem], countries: list[dict]) -> None:
    """Mutate USGS items in-place with nearest-country codes."""
    for it in items:
        if it.prestructured and it.lat is not None and it.lng is not None and not it.country_codes:
            it.country_codes = nearest_countries(it.lat, it.lng, countries)


def _build_country_name_map(countries) -> dict[str, str]:
    """Map lowercase country names (and common aliases) → ISO3 code."""
    aliases: dict[str, str] = {
        "usa": "USA", "united states": "USA", "america": "USA",
        "uk": "GBR", "britain": "GBR", "great britain": "GBR",
        "uae": "ARE", "emirates": "ARE",
        "south korea": "KOR", "korea": "KOR",
        "russia": "RUS", "ukraine": "UKR", "iran": "IRN",
        "china": "CHN", "india": "IND", "pakistan": "PAK",
        "bangladesh": "BGD", "sri lanka": "LKA",
        "saudi arabia": "SAU", "saudi": "SAU",
        "qatar": "QAT", "egypt": "EGY",
        "japan": "JPN", "germany": "DEU", "france": "FRA",
        "kenya": "KEN", "nigeria": "NGA", "ethiopia": "ETH",
    }
    m: dict[str, str] = dict(aliases)
    for c in countries:
        m[c.name.lower()] = c.code
    return m


async def run_ingestion(target_source: str | None = None) -> IngestResponse:
    cid = new_correlation_id()
    settings = get_settings()

    with session_scope() as s:
        countries = repo.all_countries(s)
        country_dicts = [{"code": c.code, "lat": c.lat, "lng": c.lng} for c in countries]
        catalog = ", ".join(f"{c.code}: {c.name}" for c in countries)
        catalog_codes = {c.code for c in countries}
        country_name_map = _build_country_name_map(countries)

        # Load existing source URLs to pre-filter before LLM call
        existing_urls: set[str] = set()
        existing_titles: set[str] = set()
        for row in s.execute(
            __import__("sqlalchemy").text("SELECT sourceUrl, title FROM ShockEvent WHERE sourceUrl IS NOT NULL")
        ).fetchall():
            if row[0]:
                existing_urls.add(row[0].strip())
            if row[1]:
                existing_titles.add(row[1].strip().lower())

    # 1-2. fetch feeds + geotag (network I/O outside the DB session)
    sources = load_sources()
    if target_source:
        sources = [s for s in sources if s.name.lower() == target_source.lower()]
        if not sources:
            raise ValueError(f"Unknown source: {target_source}")

    items = await fetch_all(sources)
    _geotag_usgs(items, country_dicts)

    # Count what we fetched before dedup
    total_fetched = len(items)
    by_source_count = {}
    for it in items:
        by_source_count[it.source] = by_source_count.get(it.source, 0) + 1
    logger.info(
        "feeds fetched",
        extra={"extra": {"total": total_fetched, "by_source": by_source_count}},
    )

    # 3. Pre-LLM dedup: drop items whose URL or normalised title already in DB
    fresh_items: list[RawItem] = []
    pre_deduped = 0
    for it in items:
        url_known = it.source_url and it.source_url.strip() in existing_urls
        title_known = it.title.strip().lower() in existing_titles
        if url_known or (title_known and it.prestructured):
            pre_deduped += 1
        else:
            fresh_items.append(it)

    logger.info(
        "pre-llm dedup",
        extra={"extra": {"fetched": total_fetched, "fresh": len(fresh_items), "pre_deduped": pre_deduped}},
    )
    items = fresh_items

    # 4. Diversity-sort: interleave sources, don't let USGS dominate
    from collections import defaultdict
    by_source: dict[str, list[RawItem]] = defaultdict(list)
    for it in items:
        by_source[it.source].append(it)

    diverse_items: list[RawItem] = []
    sources_cycle = list(by_source.keys())
    idx = 0
    max_items = settings.max_feed_items if not target_source else 30
    while sources_cycle and len(diverse_items) < max_items:
        src = sources_cycle[idx % len(sources_cycle)]
        if by_source[src]:
            diverse_items.append(by_source[src].pop(0))
            idx += 1
        else:
            sources_cycle.remove(src)

    items = diverse_items
    usgs_count = sum(1 for it in items if it.source == "USGS")
    news_count = len(items) - usgs_count

    # 5. consensus
    alpha, beta = build_clients()
    consensus = await run_consensus(alpha, beta, items, catalog, catalog_codes, country_name_map)
    logger.info(
        "consensus produced",
        extra={"extra": {"crises": len(consensus), "dual": settings.has_dual_gemini()}},
    )

    inserted = 0
    skipped = 0
    ledger_rows = 0
    inserted_events: list[dict] = []

    with session_scope() as s:
        for c in consensus:
            sev = c.shock
            ext_id = (
                f"usgs-{sev.title}" if sev.type == "earthquake" else _external_id(c)
            )
            vector = {
                "lat": sev.lat,
                "lng": sev.lng,
                "severity": sev.severity,
                "severityScore": sev.severity_score,
                "initialAsset": sev.location_name,
            }
            repo.insert_ledger(
                s,
                sourceFeedUrl=c.source_feed_url or "n/a",
                detectedShockVector=json.dumps(vector),
                agentAlphaRaw=json.dumps(c.alpha_raw),
                agentBetaRaw=json.dumps(c.beta_raw),
                byzantineAgreementDelta=c.byzantine_agreement_delta,
                calculatedCascadeDag=json.dumps({"nodes": [], "edges": []}),
            )
            ledger_rows += 1

            if repo.shock_by_external_id(s, ext_id):
                skipped += 1
                continue

            occurred = datetime.now(timezone.utc) - timedelta(
                hours=_published_hours(items, sev.title)
            )
            shock = repo.insert_shock(
                s,
                externalId=ext_id,
                source=sev.source or ("USGS" if sev.type == "earthquake" else "WebSearch"),
                sourceUrl=c.source_feed_url or None,
                title=sev.title,
                description=sev.description,
                type=sev.type,
                severity=sev.severity,
                lat=sev.lat,
                lng=sev.lng,
                locationName=sev.location_name,
                countryCodes=json.dumps(sev.country_codes),
                occurredAt=occurred,
                status="new",
                confidence=sev.confidence,
            )
            inserted += 1
            inserted_events.append({"id": shock.id, "title": shock.title, "source": shock.source})
            repo.insert_decision(
                s,
                action="ingest",
                summary=f"Ingested {shock.source} event: {shock.title}",
                actor="consensus-engine (alpha+beta+gamma)",
                metadata={
                    "shockId": shock.id,
                    "byzantineDelta": c.byzantine_agreement_delta,
                    "correlationId": cid,
                },
            )

    return IngestResponse(
        ok=True,
        usgsFetched=usgs_count,
        newsSearched=news_count,
        inserted=inserted,
        skipped=skipped,
        insertedEvents=inserted_events,
        ledgerRows=ledger_rows,
        consensusMode=settings.has_dual_gemini(),
        correlationId=cid,
    )


def _published_hours(items: list[RawItem], title: str) -> float:
    for it in items:
        if it.title == title:
            return it.published_hours_ago
    return 12.0
