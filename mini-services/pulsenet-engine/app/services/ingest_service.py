"""Ingestion service — feeds → consensus → ledger → ShockEvent rows.

Flow (one correlation id per run):
  1. load + fetch all enabled feed sources (RSS-first + USGS).
  2. geo-tag USGS items to nearest catalog countries.
  3. run Alpha ∥ Beta → Gamma consensus over the batch.
  4. write a consensus-ledger row per detected crisis (interpretability).
  5. dedupe by externalId + insert new ShockEvents + audit-trail entries.
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


async def run_ingestion(target_source: str | None = None) -> IngestResponse:
    cid = new_correlation_id()
    settings = get_settings()

    with session_scope() as s:
        countries = repo.all_countries(s)
        country_dicts = [{"code": c.code, "lat": c.lat, "lng": c.lng} for c in countries]
        catalog = ", ".join(f"{c.code}: {c.name}" for c in countries)
        catalog_codes = {c.code for c in countries}

    # 1-2. fetch feeds + geotag (network I/O outside the DB session)
    sources = load_sources()
    if target_source:
        sources = [s for s in sources if s.name.lower() == target_source.lower()]
        if not sources:
            raise ValueError(f"Unknown source: {target_source}")
        # When specifically debugging a source, increase the max limit
        settings.max_feed_items = 20

    items = await fetch_all(sources)
    _geotag_usgs(items, country_dicts)
    
    # Prioritize non-USGS sources (ACLED/Reuters) so earthquakes don't dominate the feed
    items.sort(key=lambda x: (0 if x.source != "USGS" else 1, x.published_hours_ago))

    from collections import defaultdict
    by_source = defaultdict(list)
    for it in items:
        if it.source != "USGS":
            by_source[it.source].append(it)
            
    diverse_items = []
    sources_cycle = list(by_source.keys())
    idx = 0
    while sources_cycle and len(diverse_items) < settings.max_feed_items:
        src = sources_cycle[idx % len(sources_cycle)]
        if by_source[src]:
            diverse_items.append(by_source[src].pop(0))
            idx += 1
        else:
            sources_cycle.remove(src)

    usgs_items = [it for it in items if it.source == "USGS"]
    for u in usgs_items:
        if len(diverse_items) < settings.max_feed_items:
            diverse_items.append(u)

    items = diverse_items
    usgs_count = sum(1 for it in items if it.source == "USGS")
    news_count = len(items) - usgs_count

    # 3. consensus
    alpha, beta = build_clients()
    consensus = await run_consensus(alpha, beta, items, catalog, catalog_codes)
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
            # ledger row (every detected crisis is logged — even duplicates of past runs)
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
