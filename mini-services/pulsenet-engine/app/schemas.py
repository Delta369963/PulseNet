"""Pydantic schemas = the engine's typed API contract.

These mirror the frontend `src/components/pulsenet/types.ts` shapes so the
Next.js proxy can pass JSON straight through without transformation.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["low", "moderate", "high", "severe"]
ShockType = Literal[
    "earthquake",
    "flood",
    "cyclone",
    "conflict",
    "port_closure",
    "grid_failure",
    "border_restriction",
    "strike",
]


# ---------- Feeds → raw items ----------
class RawItem(BaseModel):
    """A normalized item from any feed source (RSS/GeoJSON/API)."""

    source: str
    source_url: Optional[str] = None
    title: str
    summary: str = ""
    lang: str = "en"
    published_hours_ago: float = 12.0
    lat: Optional[float] = None
    lng: Optional[float] = None
    # Pre-structured hint (USGS gives us severity/coords directly; RSS does not).
    prestructured: bool = False
    severity: Optional[Severity] = None
    shock_type: Optional[ShockType] = None
    country_codes: list[str] = Field(default_factory=list)


# ---------- Agents → structured shock ----------
class StructuredShock(BaseModel):
    """One agent's structured extraction from a RawItem."""

    source: str = ""
    title: str
    description: str
    type: ShockType
    severity: Severity
    severity_score: int = Field(ge=1, le=10, default=5)
    location_name: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    country_codes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ConsensusShock(BaseModel):
    """Gamma's validated payload: the agreed shock + the agreement delta."""

    shock: StructuredShock
    byzantine_agreement_delta: float = Field(ge=0.0, le=1.0)
    alpha_raw: dict = Field(default_factory=dict)
    beta_raw: dict = Field(default_factory=dict)
    source_feed_url: str = ""


# ---------- API request/response ----------
class IngestResponse(BaseModel):
    ok: bool = True
    usgsFetched: int = 0
    newsSearched: int = 0
    inserted: int = 0
    skipped: int = 0
    insertedEvents: list[dict] = Field(default_factory=list)
    ledgerRows: int = 0
    consensusMode: bool = False
    correlationId: str = ""


class RippleRequest(BaseModel):
    shockId: str


class RippleResponse(BaseModel):
    ok: bool = True
    shockId: str
    exposuresCreated: int = 0
    reroutesCreated: int = 0
    note: Optional[str] = None
    correlationId: str = ""


class LedgerRow(BaseModel):
    crisisId: str
    timestamp: str
    shockId: Optional[str] = None
    sourceFeedUrl: str
    detectedShockVector: dict
    byzantineAgreementDelta: float
    humanInTheLoopOverride: bool = False
    authorizedByAdmin: Optional[str] = None


class LedgerResponse(BaseModel):
    ledger: list[LedgerRow] = Field(default_factory=list)


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "pulsenet-engine"
    version: str
    features: dict[str, bool]
    dbReachable: bool
