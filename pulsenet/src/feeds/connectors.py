"""Live feed connectors for shock signals."""

import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
import requests

GDACS_RSS = "http://www.gdacs.org/xml/rss.xml"
USGS_GEOJSON = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
REUTERS_RSS = "https://feeds.reuters.com/reuters/worldNews"

# Map country names to ISO codes (subset for demo)
COUNTRY_MAP = {
    "united states": "USA", "usa": "USA", "u.s.": "USA", "america": "USA",
    "china": "CHN", "japan": "JPN", "india": "IND", "germany": "DEU",
    "united kingdom": "GBR", "uk": "GBR", "britain": "GBR",
    "saudi arabia": "SAU", "russia": "RUS", "brazil": "BRA",
    "south africa": "ZAF", "nigeria": "NGA", "kenya": "KEN",
    "yemen": "YEM", "syria": "SYR", "myanmar": "MMR", "burma": "MMR",
    "philippines": "PHL", "thailand": "THA", "vietnam": "VNM",
    "australia": "AUS", "france": "FRA", "italy": "ITA", "spain": "ESP",
    "turkey": "TUR", "egypt": "EGY", "iraq": "IRQ", "iran": "IRN",
    "pakistan": "PAK", "bangladesh": "BGD", "nepal": "NPL",
    "ethiopia": "ETH", "sudan": "SDN", "libya": "LBY", "ukraine": "UKR",
    "poland": "POL", "netherlands": "NLD", "belgium": "BEL",
    "singapore": "SGP", "malaysia": "MYS", "indonesia": "IDN",
    "south korea": "KOR", "korea": "KOR", "mexico": "MEX", "canada": "CAN",
    "argentina": "ARG", "colombia": "COL", "peru": "PER", "chile": "CHL",
    "norway": "NOR", "sweden": "SWE", "denmark": "DNK", "finland": "FIN",
    "greece": "GRC", "portugal": "PRT", "romania": "ROU", "hungary": "HUN",
    "czech": "CZE", "austria": "AUT", "switzerland": "CHE", "israel": "ISR",
    "qatar": "QAT", "uae": "ARE", "emirates": "ARE", "kuwait": "KWT",
    "oman": "OMN", "jordan": "JOR", "lebanon": "LBN", "afghanistan": "AFG",
    "somalia": "SOM", "haiti": "HTI", "cuba": "CUB", "venezuela": "VEN",
    "algeria": "DZA", "morocco": "MAR", "tunisia": "TUN", "ghana": "GHA",
    "tanzania": "TZA", "uganda": "UGA", "mozambique": "MOZ", "angola": "AGO",
    "zambia": "ZMB", "zimbabwe": "ZWE", "malawi": "MWI", "rwanda": "RWA",
    "senegal": "SEN", "ivory coast": "CIV", "cameroon": "CMR",
    "congo": "COD", "djibouti": "DJI", "sri lanka": "LKA",
    "cambodia": "KHM", "laos": "LAO", "papua": "PNG", "fiji": "FJI",
    "new zealand": "NZL", "iceland": "ISL", "georgia": "GEO", "armenia": "ARM",
    "azerbaijan": "AZE", "kazakhstan": "KAZ", "uzbekistan": "UZB",
    "turkmenistan": "TKM", "mongolia": "MNG", "niger": "NER", "chad": "TCD",
    "mali": "MLI", "burkina": "BFA", "mauritania": "MRT", "gabon": "GAB",
    "burundi": "BDI", "eritrea": "ERI", "south sudan": "SSD",
    "guinea": "GIN", "sierra leone": "SLE", "liberia": "LBR", "togo": "TGO",
    "benin": "BEN", "namibia": "NAM", "botswana": "BWA", "lesotho": "LSO",
    "eswatini": "SWZ", "gambia": "GMB", "honduras": "HND", "guatemala": "GTM",
    "nicaragua": "NIC", "ecuador": "ECU", "bolivia": "BOL", "paraguay": "PRY",
    "uruguay": "URY", "panama": "PAN", "costa rica": "CRI", "jamaica": "JAM",
    "trinidad": "TTO", "barbados": "BRB", "bahamas": "BHS", "belize": "BLZ",
    "dominican": "DOM", "puerto rico": "PRI", "taiwan": "TWN",
    "hong kong": "HKG", "macau": "MAC", "brunei": "BRN", "timor": "TLS",
    "maldives": "MDV", "bhutan": "BTN", "kyrgyzstan": "KGZ", "tajikistan": "TJK",
    "north korea": "PRK", "belarus": "BLR", "moldova": "MDA", "albania": "ALB",
    "serbia": "SRB", "croatia": "HRV", "bulgaria": "BGR", "slovakia": "SVK",
    "lithuania": "LTU", "latvia": "LVA", "estonia": "EST", "cyprus": "CYP",
    "malta": "MLT", "luxembourg": "LUX", "monaco": "MCO", "andorra": "AND",
    "san marino": "SMR", "vatican": "VAT", "liechtenstein": "LIE",
    "montenegro": "MNE", "bosnia": "BIH", "macedonia": "MKD", "kosovo": "XKX",
    "palestine": "PSE", "western sahara": "ESH", "sahara": "ESH",
    "antarctica": "ATA", "greenland": "GRL", "falkland": "FLK",
}


def _make_event_id(source: str, unique_str: str) -> str:
    h = hashlib.md5(f"{source}:{unique_str}".encode()).hexdigest()[:12]
    return f"{source}_{h}"


def _guess_country(text: str) -> Optional[str]:
    text_lower = text.lower()
    for name, code in COUNTRY_MAP.items():
        if name in text_lower:
            return code
    return None


def _parse_gdacs_severity(title: str, description: str) -> str:
    combined = f"{title} {description}".lower()
    if "red" in combined:
        return "red"
    if "orange" in combined:
        return "orange"
    if "green" in combined:
        return "green"
    return "unknown"


def _parse_gdacs_type(title: str) -> str:
    title_lower = title.lower()
    if "earthquake" in title_lower or "eq" in title_lower:
        return "earthquake"
    if "flood" in title_lower or "fl" in title_lower:
        return "flood"
    if "cyclone" in title_lower or "tc" in title_lower or "hurricane" in title_lower:
        return "cyclone"
    if "volcano" in title_lower or "vo" in title_lower:
        return "volcano"
    return "disaster"


def fetch_gdacs_events(limit: int = 10) -> List[Dict]:
    events = []
    try:
        feed = feedparser.parse(GDACS_RSS)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            description = entry.get("description", entry.get("summary", ""))
            link = entry.get("link", "")
            event_id = _make_event_id("gdacs", link or title)

            lat, lon = None, None
            if hasattr(entry, "geo_lat") and entry.geo_lat:
                lat, lon = float(entry.geo_lat), float(entry.geo_long)
            else:
                coord_match = re.search(r"lat[itude]*[:=\s]+([-\d.]+).*lon[gitude]*[:=\s]+([-\d.]+)", description, re.I)
                if coord_match:
                    lat, lon = float(coord_match.group(1)), float(coord_match.group(2))

            country = _guess_country(f"{title} {description}")
            severity = _parse_gdacs_severity(title, description)
            event_type = _parse_gdacs_type(title)

            events.append({
                "event_id": event_id,
                "source": "GDACS",
                "event_type": event_type,
                "title": title,
                "description": description[:500],
                "country_code": country,
                "latitude": lat,
                "longitude": lon,
                "severity": severity,
                "confidence": 0.85 if severity in ("red", "orange") else 0.7,
                "raw_text": f"{title}\n{description}",
            })
    except Exception as e:
        print(f"GDACS fetch error: {e}")
    return events


def fetch_usgs_events(limit: int = 10, min_magnitude: float = 4.5) -> List[Dict]:
    events = []
    try:
        resp = requests.get(USGS_GEOJSON, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            mag = props.get("mag", 0)
            if mag < min_magnitude:
                continue
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [0, 0, 0])
            lon, lat = coords[0], coords[1]
            place = props.get("place", "")
            title = f"M{mag:.1f} earthquake - {place}"
            event_id = _make_event_id("usgs", props.get("id", str(coords)))

            country = _guess_country(place)
            severity = "red" if mag >= 6.5 else "orange" if mag >= 5.5 else "green"

            events.append({
                "event_id": event_id,
                "source": "USGS",
                "event_type": "earthquake",
                "title": title,
                "description": f"Magnitude {mag} earthquake at {place}. Tsunami: {props.get('tsunami', 0)}",
                "country_code": country,
                "latitude": lat,
                "longitude": lon,
                "severity": severity,
                "confidence": min(0.95, 0.6 + mag * 0.05),
                "raw_text": title,
            })
            if len(events) >= limit:
                break
    except Exception as e:
        print(f"USGS fetch error: {e}")
    return events


def fetch_reuters_events(limit: int = 5) -> List[Dict]:
    events = []
    try:
        feed = feedparser.parse(REUTERS_RSS)
        keywords = [
            "war", "conflict", "strike", "blockade", "sanction", "port", "shipping",
            "oil", "fuel", "gas", "lpg", "wheat", "food", "shortage", "disaster",
            "earthquake", "flood", "cyclone", "explosion", "attack", "crisis",
        ]
        for entry in feed.entries:
            title = entry.get("title", "")
            description = entry.get("description", entry.get("summary", ""))
            combined = f"{title} {description}".lower()
            if not any(kw in combined for kw in keywords):
                continue

            link = entry.get("link", "")
            event_id = _make_event_id("reuters", link or title)
            country = _guess_country(combined)

            event_type = "geopolitical"
            if any(w in combined for w in ["earthquake", "flood", "cyclone", "disaster"]):
                event_type = "disaster"
            elif any(w in combined for w in ["war", "conflict", "attack", "strike"]):
                event_type = "conflict"
            elif any(w in combined for w in ["oil", "fuel", "gas", "lpg", "wheat", "food"]):
                event_type = "supply_chain"

            events.append({
                "event_id": event_id,
                "source": "Reuters",
                "event_type": event_type,
                "title": title,
                "description": description[:500],
                "country_code": country,
                "latitude": None,
                "longitude": None,
                "severity": "orange",
                "confidence": 0.55,
                "raw_text": f"{title}\n{description}",
            })
            if len(events) >= limit:
                break
    except Exception as e:
        print(f"Reuters fetch error: {e}")
    return events


def fetch_all_feeds(gdacs_limit: int = 5, usgs_limit: int = 5, reuters_limit: int = 3) -> List[Dict]:
    all_events = []
    all_events.extend(fetch_gdacs_events(gdacs_limit))
    all_events.extend(fetch_usgs_events(usgs_limit))
    all_events.extend(fetch_reuters_events(reuters_limit))
    return all_events
