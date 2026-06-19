"""SQLAlchemy models mapped to the EXISTING Prisma-owned SQLite tables.

These mirror prisma/schema.prisma. We do NOT create/migrate tables from Python —
Prisma owns the schema (`bun run db:push`). Python only reads/writes rows.

Cuid-style ids are generated in Python so inserts match Prisma's `@default(cuid())`
expectations (any unique string id works for SQLite).
"""

from __future__ import annotations

import secrets
import time

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import datetime

class IsoDateTime(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            return value.isoformat().replace('+00:00', 'Z')
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if value > 1e11:
                return datetime.datetime.fromtimestamp(value / 1000.0, datetime.timezone.utc)
            return datetime.datetime.fromtimestamp(value, datetime.timezone.utc)
        if isinstance(value, str):
            # Check if it's a numeric string (like '1781787726713')
            clean_val = value.strip()
            if clean_val.replace('.', '', 1).isdigit():
                val_num = float(clean_val)
                if val_num > 1e11:
                    return datetime.datetime.fromtimestamp(val_num / 1000.0, datetime.timezone.utc)
                return datetime.datetime.fromtimestamp(val_num, datetime.timezone.utc)
            return datetime.datetime.fromisoformat(clean_val.replace('Z', '+00:00'))
        return value


def gen_id() -> str:
    """Collision-resistant id (cuid-like). Prisma accepts any unique string."""
    return "c" + format(int(time.time() * 1000), "x") + secrets.token_hex(8)


class Base(DeclarativeBase):
    pass


class Country(Base):
    __tablename__ = "Country"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    monitoringDensity: Mapped[float] = mapped_column(Float)
    gdpPerCapita: Mapped[float] = mapped_column(Float, default=0)
    gridDensity: Mapped[float] = mapped_column(Float, default=0)
    historicalVolatility: Mapped[float] = mapped_column(Float, default=0)
    sri: Mapped[float] = mapped_column(Float, default=0)


class Commodity(Base):
    __tablename__ = "Commodity"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)


class TradeEdge(Base):
    __tablename__ = "TradeEdge"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    supplierId: Mapped[str] = mapped_column(String)
    consumerId: Mapped[str] = mapped_column(String)
    commodityId: Mapped[str] = mapped_column(String)
    volume: Mapped[float] = mapped_column(Float)
    share: Mapped[float] = mapped_column(Float)


class ShockEvent(Base):
    __tablename__ = "ShockEvent"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    externalId: Mapped[str] = mapped_column(String, unique=True)
    source: Mapped[str] = mapped_column(String)
    sourceUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    locationName: Mapped[str] = mapped_column(String)
    countryCodes: Mapped[str] = mapped_column(Text)  # JSON array string
    occurredAt: Mapped[float] = mapped_column(IsoDateTime)
    ingestedAt: Mapped[float] = mapped_column(IsoDateTime)
    status: Mapped[str] = mapped_column(String, default="new")
    confidence: Mapped[float] = mapped_column(Float)


class ExposedRegion(Base):
    __tablename__ = "ExposedRegion"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    shockId: Mapped[str] = mapped_column(String)
    countryCode: Mapped[str] = mapped_column(String)
    countryName: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    commodityCode: Mapped[str] = mapped_column(String)
    commodityName: Mapped[str] = mapped_column(String)
    exposurePath: Mapped[str] = mapped_column(Text)
    depth: Mapped[int] = mapped_column(Integer)
    timeToShortageDays: Mapped[int] = mapped_column(Integer)
    riskScore: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    cascadeConfidence: Mapped[float] = mapped_column(Float, default=0)
    monitoringDensity: Mapped[float] = mapped_column(Float)



class RerouteSuggestion(Base):
    __tablename__ = "RerouteSuggestion"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    shockId: Mapped[str] = mapped_column(String)
    exposedRegionId: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    rationale: Mapped[str] = mapped_column(Text)
    fromSupplier: Mapped[str] = mapped_column(String)
    toSupplier: Mapped[str] = mapped_column(String)
    commodityCode: Mapped[str] = mapped_column(String)
    commodityName: Mapped[str] = mapped_column(String)
    affectedRegion: Mapped[str] = mapped_column(String)
    estimatedCostIncrease: Mapped[float] = mapped_column(Float)
    estimatedTimeToAddDays: Mapped[int] = mapped_column(Integer)
    feasibilityScore: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    monteCarloOutcome: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="pending")
    adminNote: Mapped[str | None] = mapped_column(Text, nullable=True)
    decidedAt: Mapped[float | None] = mapped_column(IsoDateTime, nullable=True)
    decidedBy: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[float] = mapped_column(IsoDateTime)


class AdminDecision(Base):
    __tablename__ = "AdminDecision"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    action: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String, default="administrator")
    metadata_: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    createdAt: Mapped[float] = mapped_column(IsoDateTime)


class SystemicConsensusLedger(Base):
    __tablename__ = "SystemicConsensusLedger"

    crisisId: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    timestamp: Mapped[float] = mapped_column(IsoDateTime)
    shockId: Mapped[str | None] = mapped_column(String, nullable=True)
    sourceFeedUrl: Mapped[str] = mapped_column(Text)
    detectedShockVector: Mapped[str] = mapped_column(Text)
    agentAlphaRaw: Mapped[str] = mapped_column(Text)
    agentBetaRaw: Mapped[str] = mapped_column(Text)
    byzantineAgreementDelta: Mapped[float] = mapped_column(Float)
    calculatedCascadeDag: Mapped[str] = mapped_column(Text)
    humanInTheLoopOverride: Mapped[bool] = mapped_column(Boolean, default=False)
    authorizedByAdmin: Mapped[str | None] = mapped_column(String, nullable=True)
