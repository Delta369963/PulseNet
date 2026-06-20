"""FastAPI app — wiring only, no business logic (logic lives in services/).

Public endpoints (called by Next.js /api proxies):
  POST /ingest             — run feeds → consensus → ledger → shocks
  POST /ingest?source=X    — ingest from a single named source
  POST /ripple             — evaluate downstream exposure + reroutes for a shock
  GET  /ledger             — recent consensus-ledger rows (Responsible-AI panel)
  GET  /health             — feature flags + DB reachability

Debug endpoints (used by the frontend debug console + backend testing):
  GET  /debug/shocks       — list all shocks with evaluation summary
  GET  /debug/shock/{id}   — full shock detail + exposures + reroutes + trade intel
  GET  /debug/feeds        — list configured feed sources + their capabilities
  POST /debug/evaluate/{id}— re-evaluate a shock, return full structured trace
"""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app import __version__
from app.config import get_settings
from app.db import models
from app.db.session import get_engine, session_scope
from app.logging import configure_logging, get_logger
from app.schemas import (
    HealthResponse,
    IngestResponse,
    LedgerResponse,
    RippleRequest,
    RippleResponse,
)
from app.services import ingest_service, ledger_service, ripple_service

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("main")

app = FastAPI(
    title="PulseNet Engine",
    version=__version__,
    description=(
        "Predictive decision-support engine — RSS ingestion, multi-agent "
        "Gemini consensus + trade intelligence, SRI cascade math. "
        "Decision-support only; no autonomous execution."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────── Core endpoints ───────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_ok = True
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as err:  # noqa: BLE001
        logger.warning("db health check failed", extra={"extra": {"err": str(err)}})
        db_ok = False
    return HealthResponse(
        version=__version__,
        features=settings.feature_flags(),
        dbReachable=db_ok,
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(source: str | None = None) -> IngestResponse:
    try:
        return await ingest_service.run_ingestion(source)
    except Exception as err:  # noqa: BLE001
        logger.exception("ingestion failed")
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.post("/ripple", response_model=RippleResponse)
async def ripple(req: RippleRequest) -> RippleResponse:
    """Async wrapper — ripple_service internally uses asyncio for trade intel."""
    try:
        return await ripple_service._evaluate_ripple_async(req.shockId)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        logger.exception("ripple evaluation failed")
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.get("/ledger", response_model=LedgerResponse)
def ledger(limit: int = 25) -> LedgerResponse:
    return ledger_service.recent_ledger(limit=limit)


# ─────────────────────── Debug endpoints ──────────────────────────────────────

@app.get("/debug/shocks")
def debug_shocks(limit: int = 50) -> dict:
    """List all shocks with their evaluation summary."""
    with session_scope() as s:
        shocks = list(s.scalars(
            select(models.ShockEvent).order_by(models.ShockEvent.ingestedAt.desc()).limit(limit)
        ).all())
        out = []
        for shock in shocks:
            exp_count = len(list(s.scalars(
                select(models.ExposedRegion).where(models.ExposedRegion.shockId == shock.id)
            ).all()))
            rer_count = len(list(s.scalars(
                select(models.RerouteSuggestion).where(models.RerouteSuggestion.shockId == shock.id)
            ).all()))
            out.append({
                "id": shock.id,
                "title": shock.title,
                "type": shock.type,
                "severity": shock.severity,
                "status": shock.status,
                "source": shock.source,
                "countryCodes": json.loads(shock.countryCodes or "[]"),
                "locationName": shock.locationName,
                "lat": shock.lat,
                "lng": shock.lng,
                "ingestedAt": shock.ingestedAt.isoformat() if shock.ingestedAt else None,
                "exposureCount": exp_count,
                "rerouteCount": rer_count,
            })
        return {"shocks": out, "total": len(out)}


@app.get("/debug/shock/{shock_id}")
def debug_shock_detail(shock_id: str) -> dict:
    """Full shock detail: metadata + exposures + reroutes + most recent ledger entry."""
    with session_scope() as s:
        shock = s.get(models.ShockEvent, shock_id)
        if not shock:
            raise HTTPException(status_code=404, detail="Shock not found")

        exposures = list(s.scalars(
            select(models.ExposedRegion).where(models.ExposedRegion.shockId == shock_id)
        ).all())
        reroutes = list(s.scalars(
            select(models.RerouteSuggestion).where(models.RerouteSuggestion.shockId == shock_id)
        ).all())
        ledger_row = s.scalars(
            select(models.SystemicConsensusLedger)
            .where(models.SystemicConsensusLedger.shockId == shock_id)
            .order_by(models.SystemicConsensusLedger.timestamp.desc())
        ).first()

        return {
            "shock": {
                "id": shock.id,
                "title": shock.title,
                "description": shock.description,
                "type": shock.type,
                "severity": shock.severity,
                "status": shock.status,
                "source": shock.source,
                "sourceUrl": shock.sourceUrl,
                "countryCodes": json.loads(shock.countryCodes or "[]"),
                "locationName": shock.locationName,
                "lat": shock.lat, "lng": shock.lng,
                "confidence": shock.confidence,
                "ingestedAt": shock.ingestedAt.isoformat() if shock.ingestedAt else None,
            },
            "tradeIntel": json.loads(ledger_row.detectedShockVector or "{}") if ledger_row else {},
            "agentContext": json.loads(ledger_row.agentAlphaRaw or "{}") if ledger_row else {},
            "exposures": [
                {
                    "id": e.id,
                    "countryName": e.countryName,
                    "countryCode": e.countryCode,
                    "commodityCode": e.commodityCode,
                    "riskScore": e.riskScore,
                    "timeToShortageDays": e.timeToShortageDays,
                    "confidence": e.confidence,
                    "cascadeConfidence": e.cascadeConfidence,
                    "exposurePath": e.exposurePath,
                }
                for e in exposures
            ],
            "reroutes": [
                {
                    "id": r.id,
                    "title": r.title,
                    "rationale": r.rationale,
                    "fromSupplier": r.fromSupplier,
                    "toSupplier": r.toSupplier,
                    "commodityCode": r.commodityCode,
                    "feasibilityScore": r.feasibilityScore,
                    "estimatedCostIncrease": r.estimatedCostIncrease,
                    "estimatedTimeToAddDays": r.estimatedTimeToAddDays,
                    "status": r.status,
                }
                for r in reroutes
            ],
        }


@app.post("/debug/evaluate/{shock_id}")
async def debug_evaluate(shock_id: str) -> dict:
    """Re-evaluate a shock and return full trace including trade intel."""
    try:
        result = await ripple_service._evaluate_ripple_async(shock_id)
        # Return full detail after evaluation
        detail = debug_shock_detail(shock_id)
        return {**result.model_dump(), **detail}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        logger.exception("debug evaluate failed")
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.get("/debug/feeds")
def debug_feeds() -> dict:
    """List all configured feed sources."""
    from app.feeds.registry import load_sources
    sources = load_sources()
    return {
        "feeds": [
            {
                "name": s.name,
                "enabled": s.enabled,
                "maxItems": getattr(s, "max_items", None),
                "isGNews": getattr(s, "_is_gnews", False),
                "url": getattr(s, "url", None),
            }
            for s in sources
        ],
        "total": len(sources),
    }


def main() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
