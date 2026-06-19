"""Repository — all DB queries/writes live here (services never touch ORM directly).

Keeping queries in one module means a schema change touches exactly one file, and
a failing DB test points straight here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Reads ----------
def all_countries(s: Session) -> list[models.Country]:
    return list(s.scalars(select(models.Country)).all())


def countries_by_codes(s: Session, codes: list[str]) -> list[models.Country]:
    if not codes:
        return []
    return list(s.scalars(select(models.Country).where(models.Country.code.in_(codes))).all())


def country_by_code(s: Session, code: str) -> models.Country | None:
    return s.scalars(select(models.Country).where(models.Country.code == code)).first()


def commodity_by_code(s: Session, code: str) -> models.Commodity | None:
    return s.scalars(select(models.Commodity).where(models.Commodity.code == code)).first()


def shock_by_id(s: Session, shock_id: str) -> models.ShockEvent | None:
    return s.get(models.ShockEvent, shock_id)


def shock_by_external_id(s: Session, external_id: str) -> models.ShockEvent | None:
    return s.scalars(
        select(models.ShockEvent).where(models.ShockEvent.externalId == external_id)
    ).first()


def edges_for_suppliers(s: Session, supplier_ids: list[str]) -> list[models.TradeEdge]:
    if not supplier_ids:
        return []
    return list(
        s.scalars(
            select(models.TradeEdge).where(models.TradeEdge.supplierId.in_(supplier_ids))
        ).all()
    )


def edges_for_consumers(s: Session, consumer_ids: list[str]) -> list[models.TradeEdge]:
    if not consumer_ids:
        return []
    return list(
        s.scalars(
            select(models.TradeEdge).where(models.TradeEdge.consumerId.in_(consumer_ids))
        ).all()
    )


def alt_edges(
    s: Session, consumer_id: str, commodity_id: str, exclude_supplier_ids: list[str]
) -> list[models.TradeEdge]:
    q = select(models.TradeEdge).where(
        models.TradeEdge.consumerId == consumer_id,
        models.TradeEdge.commodityId == commodity_id,
    )
    if exclude_supplier_ids:
        q = q.where(models.TradeEdge.supplierId.notin_(exclude_supplier_ids))
    return list(s.scalars(q).all())


def recent_ledger(s: Session, limit: int = 25) -> list[models.SystemicConsensusLedger]:
    return list(
        s.scalars(
            select(models.SystemicConsensusLedger)
            .order_by(models.SystemicConsensusLedger.timestamp.desc())
            .limit(limit)
        ).all()
    )


# ---------- Writes ----------
def insert_shock(s: Session, **fields) -> models.ShockEvent:
    fields.setdefault("ingestedAt", now())
    shock = models.ShockEvent(**fields)
    s.add(shock)
    s.flush()
    return shock


def insert_exposure(s: Session, **fields) -> models.ExposedRegion:
    row = models.ExposedRegion(**fields)
    s.add(row)
    s.flush()
    return row


def insert_reroute(s: Session, **fields) -> models.RerouteSuggestion:
    fields.setdefault("createdAt", now())
    row = models.RerouteSuggestion(**fields)
    s.add(row)
    s.flush()
    return row


def insert_decision(s: Session, action: str, summary: str, actor: str, metadata: dict | None = None):
    row = models.AdminDecision(
        action=action,
        summary=summary,
        actor=actor,
        metadata_=json.dumps(metadata) if metadata else None,
        createdAt=now(),
    )
    s.add(row)
    s.flush()
    return row


def insert_ledger(s: Session, **fields) -> models.SystemicConsensusLedger:
    fields.setdefault("timestamp", now())
    row = models.SystemicConsensusLedger(**fields)
    s.add(row)
    s.flush()
    return row


def clear_evaluation(s: Session, shock_id: str) -> None:
    """Idempotent re-eval: drop prior exposures + reroutes for this shock."""
    for r in s.scalars(
        select(models.RerouteSuggestion).where(models.RerouteSuggestion.shockId == shock_id)
    ).all():
        s.delete(r)
    for e in s.scalars(
        select(models.ExposedRegion).where(models.ExposedRegion.shockId == shock_id)
    ).all():
        s.delete(e)
    s.flush()


def set_shock_status(s: Session, shock_id: str, status: str) -> None:
    shock = s.get(models.ShockEvent, shock_id)
    if shock:
        shock.status = status
        s.flush()
