"""Database layer — SQLite (default) with optional Supabase."""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config import DB_PATH, DATA_DIR, USE_SUPABASE, SUPABASE_URL, SUPABASE_KEY

def _get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trade_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exporter TEXT NOT NULL,
            importer TEXT NOT NULL,
            commodity_hs TEXT NOT NULL,
            commodity_name TEXT NOT NULL,
            volume_usd REAL NOT NULL,
            volume_tons REAL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            source TEXT NOT NULL,
            event_type TEXT,
            title TEXT,
            description TEXT,
            country_code TEXT,
            latitude REAL,
            longitude REAL,
            severity TEXT,
            confidence REAL,
            raw_text TEXT,
            ingested_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ripple_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            country_code TEXT NOT NULL,
            commodity TEXT NOT NULL,
            exposure_type TEXT,
            time_to_shortage_days REAL,
            confidence REAL,
            monitoring_density REAL,
            low_confidence_flag INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reroute_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            rank INTEGER,
            from_country TEXT,
            to_country TEXT,
            commodity TEXT,
            alternative_supplier TEXT,
            route_description TEXT,
            estimated_delay_days REAL,
            success_probability REAL,
            confidence REAL,
            status TEXT DEFAULT 'pending',
            reviewed_at TEXT,
            reviewer_note TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suggestion_id INTEGER,
            event_id TEXT,
            action TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def seed_trade_graph(edges: List[Dict]):
    conn = _get_connection()
    conn.execute("DELETE FROM trade_edges")
    for e in edges:
        conn.execute(
            "INSERT INTO trade_edges (exporter, importer, commodity_hs, commodity_name, volume_usd, volume_tons) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (e["exporter"], e["importer"], e["commodity_hs"], e["commodity_name"],
             e["volume_usd"], e.get("volume_tons")),
        )
    conn.commit()
    conn.close()


def get_trade_edges(commodity_hs: Optional[str] = None) -> List[Dict]:
    conn = _get_connection()
    if commodity_hs:
        rows = conn.execute(
            "SELECT * FROM trade_edges WHERE commodity_hs = ?", (commodity_hs,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM trade_edges").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_event(event: Dict) -> int:
    conn = _get_connection()
    now = datetime.utcnow().isoformat()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO events
               (event_id, source, event_type, title, description, country_code,
                latitude, longitude, severity, confidence, raw_text, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.get("event_id"), event.get("source"), event.get("event_type"),
                event.get("title"), event.get("description"), event.get("country_code"),
                event.get("latitude"), event.get("longitude"), event.get("severity"),
                event.get("confidence"), event.get("raw_text"), now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM events WHERE event_id = ?", (event.get("event_id"),)).fetchone()
        conn.close()
        return row["id"] if row else 0
    except Exception:
        conn.close()
        return 0


def get_events(processed: Optional[bool] = None, limit: int = 50) -> List[Dict]:
    conn = _get_connection()
    if processed is not None:
        rows = conn.execute(
            "SELECT * FROM events WHERE processed = ? ORDER BY ingested_at DESC LIMIT ?",
            (1 if processed else 0, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY ingested_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_event_processed(event_id: str):
    conn = _get_connection()
    conn.execute("UPDATE events SET processed = 1 WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()


def save_ripple_results(event_id: str, results: List[Dict]):
    conn = _get_connection()
    now = datetime.utcnow().isoformat()
    for r in results:
        conn.execute(
            """INSERT INTO ripple_results
               (event_id, country_code, commodity, exposure_type, time_to_shortage_days,
                confidence, monitoring_density, low_confidence_flag, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, r["country_code"], r["commodity"], r.get("exposure_type"),
                r.get("time_to_shortage_days"), r.get("confidence"),
                r.get("monitoring_density"), 1 if r.get("low_confidence_flag") else 0, now,
            ),
        )
    conn.commit()
    conn.close()


def get_ripple_results(event_id: str) -> List[Dict]:
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM ripple_results WHERE event_id = ? ORDER BY time_to_shortage_days ASC",
        (event_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_reroute_suggestions(event_id: str, suggestions: List[Dict]):
    conn = _get_connection()
    now = datetime.utcnow().isoformat()
    for s in suggestions:
        conn.execute(
            """INSERT INTO reroute_suggestions
               (event_id, rank, from_country, to_country, commodity, alternative_supplier,
                route_description, estimated_delay_days, success_probability, confidence,
                status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (
                event_id, s.get("rank"), s.get("from_country"), s.get("to_country"),
                s.get("commodity"), s.get("alternative_supplier"), s.get("route_description"),
                s.get("estimated_delay_days"), s.get("success_probability"),
                s.get("confidence"), now,
            ),
        )
    conn.commit()
    conn.close()


def get_reroute_suggestions(event_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
    conn = _get_connection()
    query = "SELECT * FROM reroute_suggestions"
    params: List[Any] = []
    conditions = []
    if event_id:
        conditions.append("event_id = ?")
        params.append(event_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY rank ASC, created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_suggestion_status(suggestion_id: int, status: str, note: str = ""):
    conn = _get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE reroute_suggestions SET status = ?, reviewed_at = ?, reviewer_note = ? WHERE id = ?",
        (status, now, note, suggestion_id),
    )
    row = conn.execute("SELECT event_id FROM reroute_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
    if row:
        conn.execute(
            "INSERT INTO decisions (suggestion_id, event_id, action, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (suggestion_id, row["event_id"], status, note, now),
        )
    conn.commit()
    conn.close()


def get_decisions(limit: int = 20) -> List[Dict]:
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
