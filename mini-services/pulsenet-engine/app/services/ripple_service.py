"""Ripple service — Gemini-guided downstream-exposure + reroute evaluation.

Flow for one shock:
  1. Load shock + country objects from DB.
  2. Call Gemini Trade Intelligence → learn which commodities are disrupted,
     what the country needs, and resolve empty country codes from location text.
  3. Build OUTBOUND exposures: for each commodity Gemini says is disrupted,
     trace downstream consumers that depend on the affected suppliers.
  4. Build INBOUND/Humanitarian exposures: for each commodity Gemini says the
     country needs, generate aid-routing suggestions using global exporters.
  5. Persist exposures + reroutes, sorted by Gemini priority order.
  6. Write consensus-ledger row with the cascade DAG.

No hardcoded WHEAT/PHARMA assumptions — Gemini knows world trade.
"""

from __future__ import annotations

import asyncio
import json

from app.agents.llm import build_clients
from app.agents.trade_intel import TradeIntel, query_trade_intel
from app.compute.cascade import CascadeNode, build_cascade, recuperation_factor
from app.compute.monte_carlo import monte_carlo
from app.config import get_settings
from app.db import repo
from app.db.session import session_scope
from app.logging import get_logger, new_correlation_id
from app.schemas import RippleResponse

logger = get_logger("services.ripple")

SEVERITY_WEIGHT = {"low": 0.15, "moderate": 0.45, "high": 0.72, "severe": 1.0}

# Severity scores below this don't trigger area-of-effect expansion
SEVERITY_AOE_THRESHOLD = {"earthquake": 7, "flood": 5, "cyclone": 6, "conflict": 4}

# Country name / alias → ISO-3 mapping for location-text fallback
_COUNTRY_ALIASES: dict[str, str] = {
    "russia": "RUS", "ukraine": "UKR", "iran": "IRN", "china": "CHN",
    "india": "IND", "pakistan": "PAK", "bangladesh": "BGD",
    "saudi arabia": "SAU", "saudi": "SAU",
    "united arab emirates": "ARE", "uae": "ARE",
    "qatar": "QAT", "egypt": "EGY", "kenya": "KEN",
    "nigeria": "NGA", "ethiopia": "ETH",
    "united states": "USA", "usa": "USA", "america": "USA",
    "germany": "DEU", "france": "FRA", "japan": "JPN",
    "south korea": "KOR", "korea": "KOR",
    "philippines": "PHL", "indonesia": "IDN", "myanmar": "MMR",
    "thailand": "THA", "vietnam": "VNM", "malaysia": "MYS",
    "turkey": "TUR", "türkiye": "TUR", "syria": "SYR", "lebanon": "LBN",
    "israel": "ISR", "gaza": "PSE", "palestine": "PSE",
    "afghanistan": "AFG", "iraq": "IRQ", "yemen": "YEM",
    "somalia": "SOM", "sudan": "SDN", "libya": "LBY",
}


def _codes_from_text(text: str) -> list[str]:
    """Extract country codes by scanning text for country names/aliases."""
    t = text.lower()
    found: list[str] = []
    for name, code in sorted(_COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        if name in t and code not in found:
            found.append(code)
    return found


def evaluate_ripple(shock_id: str) -> RippleResponse:
    """Synchronous entry point — internally runs async trade intel call."""
    return asyncio.run(_evaluate_ripple_async(shock_id))


async def _evaluate_ripple_async(shock_id: str) -> RippleResponse:
    cid = new_correlation_id()
    settings = get_settings()

    with session_scope() as s:
        shock = repo.shock_by_id(s, shock_id)
        if shock is None:
            raise ValueError("Shock not found")

        repo.clear_evaluation(s, shock_id)

        # 1. Resolve country codes — use DB value, fallback to location text
        supplier_codes = json.loads(shock.countryCodes or "[]")
        if not supplier_codes:
            supplier_codes = _codes_from_text(
                f"{shock.title} {shock.locationName or ''}"
            )
            logger.info(
                "country_code_fallback",
                extra={"extra": {"shock": shock_id, "resolved": supplier_codes}},
            )

        suppliers = repo.countries_by_codes(s, supplier_codes) if supplier_codes else []

        # 2. Gemini Trade Intelligence
        alpha, _ = build_clients()
        intel: TradeIntel = await query_trade_intel(
            client=alpha,
            shock_type=shock.type,
            shock_title=shock.title,
            shock_location=shock.locationName or "",
            severity=shock.severity,
            country_codes=supplier_codes,
            country_names=[c.name for c in suppliers],
        )

        # Use Gemini-resolved codes if DB codes were missing
        if not suppliers and intel.affected_countries_hint:
            suppliers = repo.countries_by_codes(s, intel.affected_countries_hint)
            supplier_codes = [c.code for c in suppliers]

        if not suppliers:
            repo.set_shock_status(s, shock_id, "evaluated")
            repo.insert_decision(
                s,
                action="evaluate",
                summary=f'Evaluated ripple for "{shock.title}" — country unresolvable; no exposure.',
                actor="ripple-agent+trade-intel",
                metadata={"shockId": shock_id, "correlationId": cid, "intel": "no_country"},
            )
            return RippleResponse(
                ok=True,
                shockId=shock_id,
                exposuresCreated=0,
                reroutesCreated=0,
                note="Country could not be resolved from DB or Gemini.",
                correlationId=cid,
            )

        supplier_ids = [c.id for c in suppliers]
        supplier_names = " / ".join(c.name for c in suppliers)
        sev_w = SEVERITY_WEIGHT.get(shock.severity, 0.45)

        # 3. Load trade edges
        all_edges = repo.edges_for_suppliers(s, supplier_ids)
        inbound_edges = repo.edges_for_consumers(s, supplier_ids)

        # 4. Build exposure aggregation map — guided by trade intel
        agg: dict[tuple[str, str], dict] = {}

        from app.db import models
        commodity_by_id: dict[str, models.Commodity] = {}
        for e in all_edges + inbound_edges:
            if e.commodityId not in commodity_by_id:
                obj = s.get(models.Commodity, e.commodityId)
                if obj:
                    commodity_by_id[e.commodityId] = obj

        # OUTBOUND: affected countries are suppliers of disrupted commodities
        disrupted_codes = set(intel.disrupted_export_commodities)
        for e in all_edges:
            cm = commodity_by_id.get(e.commodityId)
            if cm is None:
                continue
            # Only include commodities Gemini says are disrupted
            if cm.code not in disrupted_codes:
                continue
            key = (e.consumerId, e.commodityId)
            entry = agg.setdefault(key, {
                "suppliers": [], "share": 0.0,
                "consumerId": e.consumerId, "commodityId": e.commodityId,
                "inbound": False, "virtual": False,
            })
            sup = next((c for c in suppliers if c.id == e.supplierId), None)
            entry["suppliers"].append({"name": sup.name if sup else "?", "share": e.share})
            entry["share"] += e.share

        # INBOUND: affected country needs emergency imports of these commodities
        inbound_codes = set(intel.inbound_commodities)
        _inject_inbound(s, shock, suppliers, supplier_ids, inbound_codes, agg, commodity_by_id, models)

        exposures = _build_exposures(s, agg, suppliers, supplier_ids, commodity_by_id, shock, sev_w, intel)
        # Sort by Gemini commodity priority, then by riskScore descending
        priority_map = {c: i for i, c in enumerate(intel.commodity_priority)}
        exposures.sort(key=lambda x: (priority_map.get(x["commodityCode"], 99), -x["riskScore"]))

        cascade_dag = _build_cascade_dag(shock, exposures)

        # 5. Persist exposures
        saved: list[tuple] = []
        for ex in exposures:
            if ex["riskScore"] < 8 or ex["exposureShare"] < 0.04:
                continue
            row = repo.insert_exposure(
                s,
                shockId=shock_id,
                countryCode=ex["countryCode"],
                countryName=ex["countryName"],
                region=ex["region"],
                lat=ex["lat"],
                lng=ex["lng"],
                commodityCode=ex["commodityCode"],
                commodityName=ex["commodityName"],
                exposurePath=ex["path"],
                depth=1,
                timeToShortageDays=ex["tts"],
                riskScore=ex["riskScore"],
                confidence=ex["confidence"],
                cascadeConfidence=ex["cascadeConfidence"],
                monitoringDensity=ex["monitoringDensity"],
            )
            saved.append((row, ex))

        reroutes_created = _build_reroutes(
            s, shock_id, saved, suppliers, supplier_ids, supplier_names,
            settings.monte_carlo_trials, intel,
        )

        repo.set_shock_status(s, shock_id, "evaluated")
        repo.insert_ledger(
            s,
            shockId=shock_id,
            sourceFeedUrl=shock.sourceUrl or "n/a",
            detectedShockVector=json.dumps({
                "lat": shock.lat, "lng": shock.lng,
                "severity": shock.severity, "initialAsset": shock.locationName,
                "tradeIntel": {
                    "disrupted": intel.disrupted_export_commodities,
                    "inbound": intel.inbound_commodities,
                    "fromLLM": intel.from_llm,
                },
            }),
            agentAlphaRaw=json.dumps({"contextSummary": intel.context_summary, "fromLLM": intel.from_llm}),
            agentBetaRaw=json.dumps({"note": "ripple evaluation (trade-intel guided)"}),
            byzantineAgreementDelta=0.0,
            calculatedCascadeDag=json.dumps(cascade_dag),
        )
        repo.insert_decision(
            s,
            action="evaluate",
            summary=(
                f'Evaluated ripple for "{shock.title}" — '
                f'{len(saved)} exposed regions, {reroutes_created} reroutes. '
                f'Trade intel: disrupted={intel.disrupted_export_commodities}, '
                f'inbound={intel.inbound_commodities}'
            ),
            actor="ripple-agent+trade-intel",
            metadata={
                "shockId": shock_id,
                "exposures": len(saved),
                "reroutes": reroutes_created,
                "correlationId": cid,
                "tradeIntelFromLLM": intel.from_llm,
            },
        )

    return RippleResponse(
        ok=True,
        shockId=shock_id,
        exposuresCreated=len(saved),
        reroutesCreated=reroutes_created,
        correlationId=cid,
    )


# ──────────────────────────── helpers ────────────────────────────


def _inject_inbound(s, shock, suppliers, supplier_ids, inbound_codes: set[str],
                    agg: dict, commodity_by_id: dict, models) -> None:
    """Inject inbound aid routing entries for commodities the country needs."""
    from sqlalchemy import select

    affected_ids = {c.id for c in suppliers}

    for commodity_code in inbound_codes:
        commodity = s.scalars(
            select(models.Commodity).where(models.Commodity.code == commodity_code)
        ).first()
        if not commodity:
            continue
        commodity_by_id[commodity.id] = commodity

        # Find global exporters of this commodity (not the affected country itself)
        exporter_edges = s.scalars(
            select(models.TradeEdge).where(
                models.TradeEdge.commodityId == commodity.id,
                models.TradeEdge.supplierId.notin_(list(affected_ids)),
            )
        ).all()

        exporter_vol: dict[str, float] = {}
        for e in exporter_edges:
            exporter_vol[e.supplierId] = exporter_vol.get(e.supplierId, 0) + e.volume

        top_exporters = sorted(exporter_vol.items(), key=lambda x: -x[1])[:3]

        for affected_country in suppliers:
            # Always inject for conflict high/severe; otherwise only if no existing inbound
            force = shock.type == "conflict" and shock.severity in ("high", "severe")
            existing = s.scalars(
                select(models.TradeEdge).where(
                    models.TradeEdge.consumerId == affected_country.id,
                    models.TradeEdge.commodityId == commodity.id,
                )
            ).all()
            if existing and not force:
                continue

            key = (affected_country.id, commodity.id)
            if key not in agg:
                agg[key] = {
                    "suppliers": [], "share": 0.0,
                    "consumerId": affected_country.id,
                    "commodityId": commodity.id,
                    "inbound": True, "virtual": True,
                }

            for exporter_id, _ in top_exporters:
                exporter = s.get(models.Country, exporter_id)
                if exporter:
                    agg[key]["suppliers"].append({"name": exporter.name, "share": 0.9, "virtual": True})
            agg[key]["share"] = 0.9


def _build_exposures(s, agg, suppliers, supplier_ids, commodity_by_id, shock, sev_w, intel: TradeIntel) -> list[dict]:
    out = []
    from app.db import models

    all_country_cache: dict[str, models.Country] = {c.id: c for c in suppliers}

    for (consumer_id, commodity_id), entry in agg.items():
        cm = commodity_by_id.get(commodity_id)
        if cm is None:
            obj = s.get(models.Commodity, commodity_id)
            if obj:
                commodity_by_id[commodity_id] = obj
                cm = obj
        if cm is None:
            continue

        consumer = all_country_cache.get(consumer_id)
        if consumer is None:
            obj = s.get(models.Country, consumer_id)
            if obj:
                all_country_cache[consumer_id] = obj
                consumer = obj
        if consumer is None:
            continue

        is_inbound = entry.get("inbound", False)
        is_virtual = entry.get("virtual", False)

        if is_inbound:
            # Severity scales the urgency of inbound aid
            base_risk = 60 + sev_w * 35
            exposure_share = 0.85
            tts = max(2, round(10 - sev_w * 7))
            risk = round(base_risk)
            confidence = 0.78
            cascade_confidence = round(0.6 + sev_w * 0.25, 4)
            summary = intel.context_summary or "Crisis-driven need for emergency imports."
            if is_virtual:
                path = (
                    f"[{shock.type.upper()}] {shock.title} → {consumer.name}: "
                    f"critical {cm.name} import need (no established route). {summary}"
                )
            else:
                path = (
                    f"[{shock.type.upper()}] {shock.title} → {consumer.name}: "
                    f"critical {cm.name} import need. {summary}"
                )
        else:
            # Outbound: scale by severity + event type
            type_multiplier = {
                "conflict": 0.85, "earthquake": 0.3, "flood": 0.55,
                "cyclone": 0.65, "port_closure": 0.75, "grid_failure": 0.5,
                "border_restriction": 0.8, "strike": 0.6,
            }.get(shock.type, 0.5)
            # Severe earthquakes get higher multiplier
            if shock.type == "earthquake" and shock.severity == "severe":
                type_multiplier = 0.55

            raw_share = entry["share"] * type_multiplier
            exposure_share = min(1.0, raw_share)

            tts = max(2, round(21 - 18 * exposure_share))
            risk = round(exposure_share * (65 + sev_w * 35))
            confidence = max(0.3, min(0.92, 0.3 + consumer.monitoringDensity * 0.6))
            vulnerability = 1.0 - recuperation_factor(consumer.sri if consumer.sri > 0 else 0.1)
            cascade_confidence = round(exposure_share * vulnerability, 4)
            sup_list = ", ".join(f"{x['name']} ({round(x['share'] * 100)}%)" for x in entry["suppliers"])
            path = (
                f"{shock.title} → {sup_list} export disruption → "
                f"{consumer.name} ({round(exposure_share * 100)}% of {cm.name} supply at risk)"
            )

        out.append({
            "countryCode": consumer.code,
            "countryName": consumer.name,
            "region": consumer.region,
            "lat": consumer.lat,
            "lng": consumer.lng,
            "commodityCode": cm.code,
            "commodityName": cm.name,
            "path": path,
            "tts": tts,
            "riskScore": risk,
            "confidence": confidence,
            "monitoringDensity": consumer.monitoringDensity,
            "cascadeConfidence": cascade_confidence,
            "exposureShare": exposure_share,
            "sri": consumer.sri,
            "consumerId": consumer_id,
            "commodityId": commodity_id,
            "inbound": is_inbound,
        })
    return out


def _build_cascade_dag(shock, exposures) -> dict:
    root = CascadeNode(id="root", label=shock.title, cond_prob=1.0, sri=1.0)
    children = [
        CascadeNode(
            id=f"{ex['countryCode']}-{ex['commodityCode']}",
            label=f"{ex['countryName']} {ex['commodityName']}",
            cond_prob=min(1.0, ex["exposureShare"]),
            sri=ex["sri"] or 0.5,
        )
        for ex in exposures[:12]
    ]
    return build_cascade(root, children).to_dict()


def _build_reroutes(s, shock_id, saved, suppliers, supplier_ids, supplier_names,
                    trials, intel: TradeIntel) -> int:
    from app.db import models
    from sqlalchemy import select

    count = 0
    for row, ex in saved[:12]:
        if ex["riskScore"] < 8 or ex["exposureShare"] < 0.04:
            continue
        consumer = repo.country_by_code(s, ex["countryCode"])
        commodity = repo.commodity_by_code(s, ex["commodityCode"])
        if not consumer or not commodity:
            continue

        is_inbound = ex.get("inbound", False)
        context = intel.context_summary or ""

        if is_inbound:
            # Humanitarian surge: find global suppliers of this commodity
            all_export_edges = s.scalars(
                select(models.TradeEdge).where(
                    models.TradeEdge.commodityId == commodity.id,
                    models.TradeEdge.supplierId.notin_(supplier_ids),
                    models.TradeEdge.consumerId != consumer.id,
                )
            ).all()

            exporter_vol: dict[str, float] = {}
            exporter_share: dict[str, float] = {}
            for e in all_export_edges:
                exporter_vol[e.supplierId] = exporter_vol.get(e.supplierId, 0) + e.volume
                exporter_share[e.supplierId] = max(exporter_share.get(e.supplierId, 0), e.share)
            top = sorted(exporter_vol.items(), key=lambda x: -x[1])[:3]

            for exporter_id, _ in top:
                sup = s.get(models.Country, exporter_id)
                if not sup:
                    continue
                share = exporter_share.get(exporter_id, 0.3)
                tta = max(3, round(5 + (1 - share) * 12))
                cost = round((6 + (1 - share) * 18) * 10) / 10
                feasibility = max(0.4, min(0.92, share * 0.55 + 0.42))
                confidence = max(0.42, min(0.88, ex["confidence"] * 0.8 + 0.12))
                mc = monte_carlo(ex["tts"], tta, trials=trials)
                equity = (
                    " Equity caveat: monitoring density is low — manual verification recommended."
                    if ex["monitoringDensity"] < 0.55
                    else ""
                )
                repo.insert_reroute(
                    s,
                    shockId=shock_id,
                    exposedRegionId=row.id,
                    title=f"Humanitarian Aid: {sup.name} → {ex['countryName']} [{commodity.code}]",
                    rationale=(
                        f"Surge {commodity.name} to {ex['countryName']} from {sup.name}. "
                        f"{context}{equity}"
                    ),
                    fromSupplier=sup.name,
                    toSupplier=ex["countryName"],
                    commodityCode=commodity.code,
                    commodityName=commodity.name,
                    affectedRegion=ex["countryName"],
                    estimatedCostIncrease=cost,
                    estimatedTimeToAddDays=tta,
                    feasibilityScore=feasibility,
                    confidence=confidence,
                    monteCarloOutcome=json.dumps(mc.to_dict()),
                    status="pending",
                )
                count += 1
        else:
            # Outbound: find alternate suppliers for consumers who lost supply
            alts = repo.alt_edges(s, consumer.id, commodity.id, supplier_ids)
            alts.sort(key=lambda a: a.share, reverse=True)
            for alt in alts[:2]:
                sup = s.get(models.Country, alt.supplierId)
                tta = max(3, round(7 + (1 - alt.share) * 15))
                cost = round((9 + (1 - alt.share) * 22) * 10) / 10
                feasibility = max(0.25, min(0.9, alt.share * 0.55 + 0.32))
                confidence = max(0.3, min(0.92, ex["confidence"] * 0.75 + alt.share * 0.25))
                mc = monte_carlo(ex["tts"], tta, trials=trials)
                equity = (
                    " Equity caveat: monitoring density is low — manual verification recommended."
                    if ex["monitoringDensity"] < 0.55
                    else ""
                )
                repo.insert_reroute(
                    s,
                    shockId=shock_id,
                    exposedRegionId=row.id,
                    title=f"Reroute: {ex['countryName']} {commodity.code} via {sup.name if sup else '?'}",
                    rationale=(
                        f"Replace {round(ex['exposureShare'] * 100)}% of {ex['countryName']}'s "
                        f"{commodity.name} deficit from {sup.name if sup else '?'} "
                        f"(current share: {round(alt.share * 100)}%). {context}{equity}"
                    ),
                    fromSupplier=supplier_names,
                    toSupplier=sup.name if sup else "?",
                    commodityCode=commodity.code,
                    commodityName=commodity.name,
                    affectedRegion=ex["countryName"],
                    estimatedCostIncrease=cost,
                    estimatedTimeToAddDays=tta,
                    feasibilityScore=feasibility,
                    confidence=confidence,
                    monteCarloOutcome=json.dumps(mc.to_dict()),
                    status="pending",
                )
                count += 1
    return count
