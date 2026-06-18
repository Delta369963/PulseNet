"""Agent 3 — Ripple Evaluator: time-to-shortage + reroute proposals."""

import json
import re
from typing import Dict, List

from src.config import GEMINI_API_KEY, USE_GEMINI, COUNTRY_NAMES, MONITORING_DENSITY
from src.database import get_trade_edges
from src.simulation.monte_carlo import rank_alternatives

# Base days of stock buffer by commodity (simplified)
STOCK_BUFFER_DAYS = {
    "LPG": 21,
    "Diesel": 14,
    "Wheat": 30,
}

SEVERITY_MULTIPLIER = {
    "red": 0.4,
    "orange": 0.6,
    "green": 0.85,
    "unknown": 0.7,
}


def _estimate_time_to_shortage(
    exposed: Dict,
    event: Dict,
    edges: List[Dict],
) -> float:
    """Deterministic ripple: estimate days until shortage."""
    commodity = exposed["commodity"]
    country = exposed["country_code"]
    base_buffer = STOCK_BUFFER_DAYS.get(commodity, 21)

    severity = event.get("severity", "orange")
    severity_mult = SEVERITY_MULTIPLIER.get(severity, 0.7)

    exposure_type = exposed.get("exposure_type", "downstream")
    depth = exposed.get("depth", 1)

    type_mult = {
        "origin": 0.5,
        "direct": 0.7,
        "downstream": 1.0,
        "import_dependent": 0.8,
        "unknown_origin": 1.2,
    }.get(exposure_type, 1.0)

    # Trade volume dependency — higher import share = faster shortage
    import_volume = sum(
        e["volume_usd"] for e in edges
        if e["importer"] == country and e["commodity_name"] == commodity
    )
    total_volume = sum(e["volume_usd"] for e in edges if e["commodity_name"] == commodity)
    dependency_ratio = import_volume / total_volume if total_volume > 0 else 0.1
    dependency_mult = 0.5 + dependency_ratio

    days = base_buffer * severity_mult * type_mult * dependency_mult
    days += depth * 3  # downstream lag

    monitoring = exposed.get("monitoring_density", 0.5)
    if monitoring < 0.4:
        days *= 0.85  # shortages may appear faster in under-monitored regions

    return round(max(3, days), 1)


def _find_alternative_suppliers(
    country: str,
    commodity: str,
    excluded: List[str],
    edges: List[Dict],
) -> List[str]:
    """Find other exporters of the same commodity to the affected country."""
    suppliers = set()
    for e in edges:
        if e["commodity_name"] == commodity and e["importer"] == country:
            if e["exporter"] not in excluded:
                suppliers.add(e["exporter"])

    # Global exporters of commodity
    global_exporters = set()
    for e in edges:
        if e["commodity_name"] == commodity and e["exporter"] not in excluded:
            global_exporters.add(e["exporter"])

    # Prefer existing trade partners, then global
    result = list(suppliers)
    for ex in global_exporters:
        if ex not in result:
            result.append(ex)

    return result[:5]


def _build_reroute_description(from_c: str, to_c: str, commodity: str) -> str:
    from_name = COUNTRY_NAMES.get(from_c, from_c)
    to_name = COUNTRY_NAMES.get(to_c, to_c)
    return f"Reroute {commodity} supply from {from_name} ({from_c}) to {to_name} ({to_c}) via alternate shipping corridor"


def _gemini_reroute_narrative(event: Dict, suggestions: List[Dict]) -> List[Dict]:
    if not USE_GEMINI or not GEMINI_API_KEY:
        return suggestions

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""Given this shock event and reroute suggestions, provide brief (1 sentence) 
actionable route descriptions. Return JSON array with same order:
[{{"route_description": "..."}}]

Event: {event.get('title', '')} ({event.get('event_type', '')}, severity: {event.get('severity', '')})
Suggestions: {json.dumps([{'from': s['alternative_supplier'], 'to': s['to_country'], 'commodity': s['commodity']} for s in suggestions])}
"""
        response = model.generate_content(prompt)
        content = response.text.strip()
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            narratives = json.loads(json_match.group())
            for i, s in enumerate(suggestions):
                if i < len(narratives):
                    s["route_description"] = narratives[i].get("route_description", s["route_description"])
    except Exception as e:
        print(f"Gemini reroute narrative failed: {e}")

    return suggestions


def evaluate_ripple(event: Dict, exposed_regions: List[Dict]) -> Dict:
    """
    Estimate time-to-shortage per region and propose ranked reroutes.
    """
    edges = get_trade_edges()
    origin = event.get("country_code", "")
    severity = event.get("severity", "orange")
    disruption = SEVERITY_MULTIPLIER.get(severity, 0.7)

    ripple_results = []
    for exposed in exposed_regions:
        days = _estimate_time_to_shortage(exposed, event, edges)
        monitoring = exposed.get("monitoring_density", MONITORING_DENSITY.get(exposed["country_code"], 0.35))
        low_conf = exposed.get("low_confidence_flag", monitoring < 0.4)

        confidence = min(0.95, 0.4 + monitoring * 0.5)
        if low_conf:
            confidence = min(confidence, 0.45)

        ripple_results.append({
            "country_code": exposed["country_code"],
            "commodity": exposed["commodity"],
            "exposure_type": exposed.get("exposure_type"),
            "time_to_shortage_days": days,
            "confidence": round(confidence, 3),
            "monitoring_density": monitoring,
            "low_confidence_flag": low_conf,
        })

    ripple_results.sort(key=lambda x: x["time_to_shortage_days"])

    # Build reroute alternatives for top 3 most urgent regions
    alternatives = []
    excluded = [origin] if origin else []
    seen_routes = set()

    for ripple in ripple_results[:3]:
        country = ripple["country_code"]
        commodity = ripple["commodity"]
        alt_suppliers = _find_alternative_suppliers(country, commodity, excluded, edges)

        for supplier in alt_suppliers[:2]:
            route_key = (supplier, country, commodity)
            if route_key in seen_routes:
                continue
            seen_routes.add(route_key)

            supplier_monitoring = MONITORING_DENSITY.get(supplier, 0.35)
            base_delay = 10 + ripple["time_to_shortage_days"] * 0.3
            base_success = 0.5 + supplier_monitoring * 0.35

            alternatives.append({
                "from_country": origin or supplier,
                "to_country": country,
                "commodity": commodity,
                "alternative_supplier": supplier,
                "route_description": _build_reroute_description(supplier, country, commodity),
                "base_delay_days": base_delay,
                "base_success_prob": base_success,
                "monitoring_density": supplier_monitoring,
                "low_confidence_flag": supplier_monitoring < 0.4,
            })

    ranked = rank_alternatives(alternatives[:6], disruption_severity=1 - disruption)

    for r in ranked:
        r["confidence"] = round(
            r.get("confidence", 0.5) * (0.7 if r.get("low_confidence_flag") else 1.0), 3
        )

    ranked = _gemini_reroute_narrative(event, ranked)

    return {
        "ripple_results": ripple_results,
        "reroute_suggestions": ranked[:3],
    }
