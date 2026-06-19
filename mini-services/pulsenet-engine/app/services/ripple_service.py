"""Ripple service — deterministic downstream-exposure + reroute evaluation.

Mirrors src/lib/pulsenet/ripple.ts (graph traversal + exposure aggregation +
Monte Carlo), and additionally:
  - uses the consumer's SRI in the cascade-confidence formula (prompt §4),
  - writes a consensus-ledger row containing the computed cascade DAG.

HUMANITARIAN SURGE LOGIC (generalised):
  For any shock at severity moderate+ (conflict, earthquake, flood, cyclone,
  port_closure), the evaluator generates inbound aid-routing suggestions for the
  disaster-stricken country itself:
    - Queries all countries that EXPORT PHARMA and WHEAT (the two emergency aid
      commodities) to find potential surge suppliers.
    - Injects virtual "inbound" exposure records for the affected country if it
      lacks pre-existing import edges for those commodities.
    - Produces "Humanitarian Surge" reroute cards directing aid FROM global
      suppliers TO the disaster-stricken country.

All math is deterministic (numpy/networkx). No LLM is required.
"""

from __future__ import annotations

import json

from app.compute.cascade import CascadeNode, build_cascade, recuperation_factor

from app.compute.monte_carlo import monte_carlo
from app.config import get_settings
from app.db import repo
from app.db.session import session_scope
from app.logging import get_logger, new_correlation_id
from app.schemas import RippleResponse

logger = get_logger("services.ripple")

SEVERITY_WEIGHT = {"low": 0.2, "moderate": 0.5, "high": 0.75, "severe": 1.0}

# Disasters that always trigger humanitarian inbound routing
HUMANITARIAN_TRIGGERS = frozenset(("conflict", "cyclone", "flood", "earthquake", "port_closure", "grid_failure"))
HUMANITARIAN_MIN_SEVERITY = {"moderate", "high", "severe"}

# Aid commodities to route TO the stricken country
AID_COMMODITIES = ["PHARMA", "WHEAT"]


def evaluate_ripple(shock_id: str) -> RippleResponse:
    cid = new_correlation_id()
    settings = get_settings()

    with session_scope() as s:
        shock = repo.shock_by_id(s, shock_id)
        if shock is None:
            raise ValueError("Shock not found")

        repo.clear_evaluation(s, shock_id)
        supplier_codes = json.loads(shock.countryCodes or "[]")
        resolved = repo.countries_by_codes(s, supplier_codes) if supplier_codes else []

        if not supplier_codes or not resolved:
            # No known affected country — check if we can still do humanitarian logic
            repo.set_shock_status(s, shock_id, "evaluated")
            repo.insert_decision(
                s,
                action="evaluate",
                summary=f'Evaluated ripple for "{shock.title}" — no mapped suppliers; no exposure.',
                actor="ripple-agent",
                metadata={"shockId": shock_id, "correlationId": cid},
            )
            return RippleResponse(
                ok=True,
                shockId=shock_id,
                exposuresCreated=0,
                reroutesCreated=0,
                note="No mapped supplier countries for this event.",
                correlationId=cid,
            )

        suppliers = repo.countries_by_codes(s, supplier_codes)
        supplier_ids = [c.id for c in suppliers]
        supplier_names = " / ".join(c.name for c in suppliers)
        sev_w = SEVERITY_WEIGHT.get(shock.severity, 0.5)

        # --- OUTBOUND: trade edges where affected countries are suppliers ---
        edges = repo.edges_for_suppliers(s, supplier_ids)

        # --- INBOUND: existing edges where affected countries are consumers ---
        inbound_edges = repo.edges_for_consumers(s, supplier_ids)

        consumer_ids = {e.consumerId for e in edges}
        for e in inbound_edges:
            consumer_ids.add(e.consumerId)

        commodity_ids = {e.commodityId for e in edges}.union({e.commodityId for e in inbound_edges})
        consumers = {c.id: c for c in suppliers}  # warm cache; extend below
        for cid_ in consumer_ids:
            if cid_ not in consumers:
                obj = s.get(type(suppliers[0]), cid_) if suppliers else None
                if obj:
                    consumers[cid_] = obj
        commodities = {}
        from app.db import models

        for mid in commodity_ids:
            obj = s.get(models.Commodity, mid)
            if obj:
                commodities[mid] = obj

        # Aggregate exposure per (consumer, commodity).
        agg: dict[tuple[str, str], dict] = {}

        # Outbound: affected countries are suppliers → consumers lose imports
        for e in edges:
            key = (e.consumerId, e.commodityId)
            entry = agg.setdefault(
                key, {"suppliers": [], "share": 0.0, "consumerId": e.consumerId, "commodityId": e.commodityId, "inbound": False}
            )
            sup = next((c for c in suppliers if c.id == e.supplierId), None)
            entry["suppliers"].append({"name": sup.name if sup else "?", "share": e.share})
            entry["share"] += e.share

        # Inbound (existing): affected country needs things it was importing
        is_humanitarian = (
            shock.type in HUMANITARIAN_TRIGGERS
            and shock.severity in HUMANITARIAN_MIN_SEVERITY
        )
        if is_humanitarian:
            for e in inbound_edges:
                key = (e.consumerId, e.commodityId)
                entry = agg.setdefault(
                    key, {"suppliers": [], "share": 0.0, "consumerId": e.consumerId, "commodityId": e.commodityId, "inbound": True}
                )
                sup = s.get(models.Country, e.supplierId)
                if sup:
                    entry["suppliers"].append({"name": sup.name, "share": e.share})
                entry["share"] += e.share

        # HUMANITARIAN SURGE: inject virtual inbound routes for PHARMA+WHEAT
        # even if the affected country has no pre-existing import edges for those
        if is_humanitarian:
            _inject_humanitarian_virtual_edges(s, shock, suppliers, agg, models)

        exposures = _build_exposures(s, agg, consumers, commodities, shock, sev_w)
        exposures.sort(key=lambda x: x["riskScore"], reverse=True)

        cascade_dag = _build_cascade_dag(shock, exposures)

        # Persist exposures.
        saved = []
        for ex in exposures:
            if ex["riskScore"] < 10 or ex["exposureShare"] < 0.05:
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
            s, shock_id, saved, suppliers, supplier_ids, supplier_names, settings.monte_carlo_trials
        )

        repo.set_shock_status(s, shock_id, "evaluated")
        repo.insert_ledger(
            s,
            shockId=shock_id,
            sourceFeedUrl=shock.sourceUrl or "n/a",
            detectedShockVector=json.dumps(
                {"lat": shock.lat, "lng": shock.lng, "severity": shock.severity, "initialAsset": shock.locationName}
            ),
            agentAlphaRaw=json.dumps({"note": "ripple evaluation (deterministic)"}),
            agentBetaRaw=json.dumps({"note": "ripple evaluation (deterministic)"}),
            byzantineAgreementDelta=0.0,
            calculatedCascadeDag=json.dumps(cascade_dag),
        )
        repo.insert_decision(
            s,
            action="evaluate",
            summary=f'Evaluated ripple for "{shock.title}" — {len(saved)} exposed regions, {reroutes_created} reroutes.',
            actor="ripple-agent",
            metadata={"shockId": shock_id, "exposures": len(saved), "reroutes": reroutes_created, "correlationId": cid},
        )

    return RippleResponse(
        ok=True,
        shockId=shock_id,
        exposuresCreated=len(saved),
        reroutesCreated=reroutes_created,
        correlationId=cid,
    )


def _inject_humanitarian_virtual_edges(s, shock, affected_countries, agg: dict, models) -> None:
    """Inject virtual inbound aid edges for PHARMA and WHEAT to disaster-stricken countries.

    For each affected country, finds global exporters of PHARMA/WHEAT that are
    NOT the affected country itself, and adds a virtual entry to `agg` so the
    evaluator will generate Humanitarian Surge reroute suggestions.
    """
    from sqlalchemy import select

    affected_ids = {c.id for c in affected_countries}

    for commodity_code in AID_COMMODITIES:
        commodity = s.scalars(
            select(models.Commodity).where(models.Commodity.code == commodity_code)
        ).first()
        if not commodity:
            continue

        # Find countries that export this commodity (existing edges with non-affected suppliers)
        all_export_edges = s.scalars(
            select(models.TradeEdge).where(
                models.TradeEdge.commodityId == commodity.id,
                models.TradeEdge.supplierId.notin_(list(affected_ids)),
            )
        ).all()

        # Collect distinct exporters by total export volume (proxy for capacity)
        exporter_volume: dict[str, float] = {}
        for e in all_export_edges:
            exporter_volume[e.supplierId] = exporter_volume.get(e.supplierId, 0) + e.volume

        # Pick top 3 exporters
        top_exporters = sorted(exporter_volume.items(), key=lambda x: -x[1])[:3]

        for affected_country in affected_countries:
            # Check if this country already has inbound edges for this commodity
            existing_inbound = s.scalars(
                select(models.TradeEdge).where(
                    models.TradeEdge.consumerId == affected_country.id,
                    models.TradeEdge.commodityId == commodity.id,
                )
            ).all()
            already_covered = bool(existing_inbound)

            # Inject virtual edges for countries without existing supply
            # (or always inject for conflict at high+ severity)
            force_inject = shock.severity in ("high", "severe") and shock.type == "conflict"
            if already_covered and not force_inject:
                continue

            # Mark the affected country as a virtual consumer
            key = (affected_country.id, commodity.id)
            if key not in agg:
                agg[key] = {
                    "suppliers": [],
                    "share": 0.0,
                    "consumerId": affected_country.id,
                    "commodityId": commodity.id,
                    "inbound": True,
                    "virtual": True,
                }

            for exporter_id, _ in top_exporters:
                exporter = s.get(models.Country, exporter_id)
                if not exporter:
                    continue
                # Use share=0.9 for virtual edges — represents the full gap to be filled
                agg[key]["suppliers"].append({"name": exporter.name, "share": 0.9, "virtual": True})
                agg[key]["share"] = max(agg[key]["share"], 0.9)


def _build_exposures(s, agg, consumers, commodities, shock, sev_w) -> list[dict]:
    out = []
    for (consumer_id, commodity_id), entry in agg.items():
        consumer = consumers.get(consumer_id)
        commodity = commodities.get(commodity_id)

        # Load missing consumers (happens for virtual edges)
        if consumer is None:
            from app.db import models
            obj = s.get(models.Country, consumer_id)
            if obj:
                consumers[consumer_id] = obj
                consumer = obj
        if commodity is None:
            from app.db import models
            obj = s.get(models.Commodity, commodity_id)
            if obj:
                commodities[commodity_id] = obj
                commodity = obj

        if consumer is None or commodity is None:
            continue

        is_inbound = entry.get("inbound", False)
        is_virtual = entry.get("virtual", False)

        if is_inbound:
            exposure_share = 0.90
            tts = 3
            risk = round(75 + SEVERITY_WEIGHT.get(shock.severity, 0.5) * 25)
            vulnerability = 0.85
            cascade_confidence = 0.85
            confidence = 0.85
            if is_virtual:
                # Virtual edge — lower confidence, labelled clearly
                path = (
                    f"[{shock.type.upper()}] Crisis in {consumer.name} — no established import route. "
                    f"Emergency {commodity.name} surge from global suppliers required."
                )
            else:
                path = (
                    f"[{shock.type.upper()}] Domestic crisis → {consumer.name} requires critical "
                    f"humanitarian import of {commodity.name}"
                )
        else:
            # Outbound: affected country was a supplier, consumers lose imports
            event_multiplier = 0.1 if shock.type in ["earthquake", "flood"] else 1.0
            if shock.type == "earthquake" and shock.severity == "severe":
                event_multiplier = 0.4
            if shock.type == "conflict":
                event_multiplier = 0.85  # Conflict disrupts exports significantly

            raw_share = entry["share"] * event_multiplier
            exposure_share = min(1.0, raw_share)

            tts = max(2, round(18 - 16 * exposure_share))
            risk = round(exposure_share * (70 + sev_w * 30))
            confidence = max(0.3, min(0.95, 0.3 + consumer.monitoringDensity * 0.6))
            vulnerability = 1.0 - recuperation_factor(consumer.sri if consumer.sri > 0 else 0.1)
            cascade_confidence = round(exposure_share * vulnerability, 4)
            sup_list = ", ".join(f"{x['name']} ({round(x['share'] * 100)}%)" for x in entry["suppliers"])
            path = (
                f"{shock.title} → {sup_list} export halt → "
                f"{consumer.name} ({round(exposure_share * 100)}% of {commodity.name} imports)"
            )

        out.append(
            {
                "countryCode": consumer.code,
                "countryName": consumer.name,
                "region": consumer.region,
                "lat": consumer.lat,
                "lng": consumer.lng,
                "commodityCode": commodity.code,
                "commodityName": commodity.name,
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
            }
        )
    return out


def _build_cascade_dag(shock, exposures) -> dict:
    root = CascadeNode(id="root", label=shock.title, cond_prob=1.0, sri=1.0)
    children = [
        CascadeNode(
            id=f"{ex['countryCode']}-{ex['commodityCode']}",
            label=f"{ex['countryName']} {ex['commodityName']} shortage",
            cond_prob=min(1.0, ex["exposureShare"]),
            sri=ex["sri"] or 0.5,
        )
        for ex in exposures
    ]
    return build_cascade(root, children).to_dict()


def _build_reroutes(s, shock_id, saved, suppliers, supplier_ids, supplier_names, trials) -> int:
    from app.db import models

    count = 0
    for row, ex in saved[:10]:  # Increased from 7 to 10 to surface more humanitarian options
        if ex["riskScore"] < 10 or ex["exposureShare"] < 0.05:
            continue
        consumer = repo.country_by_code(s, ex["countryCode"])
        commodity = repo.commodity_by_code(s, ex["commodityCode"])
        if not consumer or not commodity:
            continue

        is_inbound = ex.get("inbound", False)

        if is_inbound:
            # Humanitarian surge: find suppliers of this commodity globally
            from sqlalchemy import select
            all_export_edges = s.scalars(
                select(models.TradeEdge).where(
                    models.TradeEdge.commodityId == commodity.id,
                    models.TradeEdge.supplierId.notin_(supplier_ids),
                    models.TradeEdge.consumerId != consumer.id,
                )
            ).all()
            # Group by exporter, pick top 3 by volume
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
                tta = max(3, round(6 + (1 - exporter_share.get(exporter_id, 0.3)) * 12))
                cost = round((8 + (1 - exporter_share.get(exporter_id, 0.3)) * 20) * 10) / 10
                feasibility = max(0.4, min(0.9, exporter_share.get(exporter_id, 0.3) * 0.6 + 0.4))
                confidence = max(0.4, min(0.88, ex["confidence"] * 0.8 + 0.1))
                mc = monte_carlo(ex["tts"], tta, trials=trials)
                equity = (
                    " Equity caveat: monitoring density is low — manual verification recommended."
                    if ex["monitoringDensity"] < 0.55
                    else ""
                )
                title = f"Humanitarian Surge {ex['countryName']} {commodity.name}: {sup.name} → {ex['countryName']}"
                rationale = (
                    f"Surge {commodity.name} supplies from {sup.name} to {ex['countryName']} "
                    f"to address crisis-driven {commodity.name} shortage. "
                    f"{sup.name} has established export capacity.{equity}"
                )
                repo.insert_reroute(
                    s,
                    shockId=shock_id,
                    exposedRegionId=row.id,
                    title=title,
                    rationale=rationale,
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
            # Outbound: affected country was a supplier → find alternate suppliers
            alts = repo.alt_edges(s, consumer.id, commodity.id, supplier_ids)
            alts.sort(key=lambda a: a.share, reverse=True)
            for alt in alts[:2]:
                sup = s.get(models.Country, alt.supplierId)
                tta = max(3, round(8 + (1 - alt.share) * 14))
                cost = round((10 + (1 - alt.share) * 25) * 10) / 10
                feasibility = max(0.25, min(0.9, alt.share * 0.6 + 0.3))
                confidence = max(0.3, min(0.92, ex["confidence"] * 0.8 + alt.share * 0.2))
                mc = monte_carlo(ex["tts"], tta, trials=trials)
                equity = (
                    " Equity caveat: monitoring density is low — manual verification recommended."
                    if ex["monitoringDensity"] < 0.55
                    else ""
                )
                title = f"Reroute {ex['countryName']} {commodity.name}: {supplier_names} → {sup.name if sup else '?'}"
                rationale = (
                    f"Substitute {round(ex['exposureShare'] * 100)}% of {ex['countryName']}'s "
                    f"{commodity.name} deficit with {sup.name if sup else '?'}, which already supplies "
                    f"{round(alt.share * 100)}%.{equity}"
                )
                repo.insert_reroute(
                    s,
                    shockId=shock_id,
                    exposedRegionId=row.id,
                    title=title,
                    rationale=rationale,
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
