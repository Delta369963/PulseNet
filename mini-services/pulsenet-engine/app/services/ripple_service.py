"""Ripple service — deterministic downstream-exposure + reroute evaluation.

Mirrors src/lib/pulsenet/ripple.ts (graph traversal + exposure aggregation +
Monte Carlo), and additionally:
  - uses the consumer's SRI in the cascade-confidence formula (prompt §4),
  - writes a consensus-ledger row containing the computed cascade DAG.

All math is deterministic (numpy/networkx). No LLM is required; reroute titles
use a clear deterministic template (the optional LLM enrichment lives in the TS
fallback / can be added later without changing this contract).
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


def evaluate_ripple(shock_id: str) -> RippleResponse:
    cid = new_correlation_id()
    settings = get_settings()

    with session_scope() as s:
        shock = repo.shock_by_id(s, shock_id)
        if shock is None:
            raise ValueError("Shock not found")

        repo.clear_evaluation(s, shock_id)
        supplier_codes = json.loads(shock.countryCodes or "[]")
        # A code may not resolve to a real catalog country (honest "no risk").
        resolved = repo.countries_by_codes(s, supplier_codes) if supplier_codes else []

        if not supplier_codes or not resolved:

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

        edges = repo.edges_for_suppliers(s, supplier_ids)
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
        for e in edges:
            key = (e.consumerId, e.commodityId)
            entry = agg.setdefault(
                key, {"suppliers": [], "share": 0.0, "consumerId": e.consumerId, "commodityId": e.commodityId, "inbound": False}
            )
            sup = next((c for c in suppliers if c.id == e.supplierId), None)
            entry["suppliers"].append({"name": sup.name if sup else "?", "share": e.share})
            entry["share"] += e.share

        if shock.type in ["conflict", "cyclone", "flood", "earthquake"] and shock.severity in ["high", "severe"]:
            for e in inbound_edges:
                key = (e.consumerId, e.commodityId)
                entry = agg.setdefault(
                    key, {"suppliers": [], "share": 0.0, "consumerId": e.consumerId, "commodityId": e.commodityId, "inbound": True}
                )
                sup = s.get(models.Country, e.supplierId)
                if sup:
                    entry["suppliers"].append({"name": sup.name, "share": e.share})
                entry["share"] += e.share

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


def _build_exposures(s, agg, consumers, commodities, shock, sev_w) -> list[dict]:
    out = []
    for (consumer_id, commodity_id), entry in agg.items():
        consumer = consumers.get(consumer_id)
        commodity = commodities.get(commodity_id)
        if consumer is None or commodity is None:
            continue
        is_inbound = entry.get("inbound", False)
        
        if is_inbound:
            exposure_share = 0.95
            tts = 2
            risk = round(80 + sev_w * 20)
            vulnerability = 0.9
            cascade_confidence = 0.9
            path = f"[{shock.type.upper()}] Domestic crisis → {consumer.name} requires critical humanitarian import of {commodity.name}"
            confidence = 0.9
        else:
            # Mitigate logic flaw: localized events (earthquakes/floods) rarely halt global exports
            # unless they are incredibly severe. We penalize their exposure share.
            event_multiplier = 0.1 if shock.type in ["earthquake", "flood"] else 1.0
            if shock.type == "earthquake" and shock.severity == "severe":
                event_multiplier = 0.4
                
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
    for row, ex in saved[:7]:
        if ex["riskScore"] < 10 or ex["exposureShare"] < 0.05:
            continue
        consumer = repo.country_by_code(s, ex["countryCode"])
        commodity = repo.commodity_by_code(s, ex["commodityCode"])
        if not consumer or not commodity:
            continue
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
            
            # Use humanitarian-specific language for inbound aid routes
            if "Humanitarian" in ex["path"] or "Domestic crisis" in ex["path"]:
                title = f"Humanitarian Surge {ex['countryName']} {commodity.name}: {sup.name if sup else '?'} → {ex['countryName']}"
                rationale = (
                    f"Surge {commodity.name} supplies from {sup.name if sup else '?'} "
                    f"to {ex['countryName']} to address domestic crisis shortages. They currently supply "
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
