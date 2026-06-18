"""Agent 2 — Graph Explorer: find exposed regions via trade dependency graph."""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from src.config import MONITORING_DENSITY, COMMODITY_HS
from src.database import get_trade_edges


def _build_graph(edges: List[Dict]) -> Tuple[Dict, Dict]:
    """Build exporter→importer adjacency and reverse dependency maps per commodity."""
    forward: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
    reverse: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))

    for e in edges:
        commodity = e["commodity_name"]
        forward[e["exporter"]][commodity].append(e)
        reverse[e["importer"]][commodity].append(e)

    return forward, reverse


def _downstream_traversal(
    start: str,
    commodity: str,
    forward: Dict,
    max_depth: int = 3,
) -> List[Dict]:
    """BFS downstream from exporter to find dependent importers."""
    exposed = []
    visited: Set[Tuple[str, str]] = set()
    queue = [(start, commodity, 0, "direct")]

    while queue:
        country, comm, depth, exposure_type = queue.pop(0)
        key = (country, comm)
        if key in visited:
            continue
        visited.add(key)

        if depth > 0:
            exposed.append({
                "country_code": country,
                "commodity": comm,
                "exposure_type": exposure_type,
                "depth": depth,
            })

        if depth >= max_depth:
            continue

        for edge in forward.get(country, {}).get(comm, []):
            importer = edge["importer"]
            if (importer, comm) not in visited:
                next_type = "downstream" if depth > 0 else "direct"
                queue.append((importer, comm, depth + 1, next_type))

    return exposed


def _infer_commodities(event_type: str, severity: str) -> List[str]:
    """Map event types to likely affected commodities."""
    mapping = {
        "earthquake": ["LPG", "Diesel", "Wheat"],
        "flood": ["Wheat", "Diesel"],
        "cyclone": ["LPG", "Diesel", "Wheat"],
        "volcano": ["Diesel", "LPG"],
        "disaster": ["LPG", "Diesel", "Wheat"],
        "conflict": ["Diesel", "LPG", "Wheat"],
        "geopolitical": ["LPG", "Diesel", "Wheat"],
        "supply_chain": ["LPG", "Diesel", "Wheat"],
    }
    commodities = mapping.get(event_type, ["LPG", "Diesel", "Wheat"])
    if severity == "red":
        return commodities
    return commodities[:2]


def explore_graph(event: Dict) -> List[Dict]:
    """
    Given a structured event, find directly affected and downstream-dependent regions.
    Returns list of exposed region/commodity pairs with monitoring metadata.
    """
    edges = get_trade_edges()
    forward, reverse = _build_graph(edges)

    origin = event.get("country_code")
    event_type = event.get("event_type", "disaster")
    severity = event.get("severity", "orange")
    commodities = _infer_commodities(event_type, severity)

    all_exposed: List[Dict] = []
    seen: Set[Tuple[str, str]] = set()

    # Origin country is directly affected
    if origin:
        for comm in commodities:
            key = (origin, comm)
            if key not in seen:
                seen.add(key)
                monitoring = MONITORING_DENSITY.get(origin, 0.35)
                all_exposed.append({
                    "country_code": origin,
                    "commodity": comm,
                    "exposure_type": "origin",
                    "depth": 0,
                    "monitoring_density": monitoring,
                    "low_confidence_flag": monitoring < 0.4,
                })

        # Downstream from origin as exporter
        for comm in commodities:
            downstream = _downstream_traversal(origin, comm, forward)
            for d in downstream:
                key = (d["country_code"], d["commodity"])
                if key not in seen:
                    seen.add(key)
                    code = d["country_code"]
                    monitoring = MONITORING_DENSITY.get(code, 0.35)
                    all_exposed.append({
                        **d,
                        "monitoring_density": monitoring,
                        "low_confidence_flag": monitoring < 0.4,
                    })

        # Upstream importers that depend on origin as supplier
        for comm in commodities:
            for edge in reverse.get(origin, {}).get(comm, []):
                importer = edge["importer"]
                key = (importer, comm)
                if key not in seen:
                    seen.add(key)
                    monitoring = MONITORING_DENSITY.get(importer, 0.35)
                    all_exposed.append({
                        "country_code": importer,
                        "commodity": comm,
                        "exposure_type": "import_dependent",
                        "depth": 1,
                        "monitoring_density": monitoring,
                        "low_confidence_flag": monitoring < 0.4,
                    })

    # If no origin, flag high-risk low-monitoring regions for manual review
    if not origin:
        low_monitoring = [
            code for code, score in MONITORING_DENSITY.items() if score < 0.4
        ]
        for code in low_monitoring[:5]:
            for comm in commodities[:1]:
                key = (code, comm)
                if key not in seen:
                    seen.add(key)
                    all_exposed.append({
                        "country_code": code,
                        "commodity": comm,
                        "exposure_type": "unknown_origin",
                        "depth": -1,
                        "monitoring_density": MONITORING_DENSITY.get(code, 0.3),
                        "low_confidence_flag": True,
                    })

    return all_exposed
