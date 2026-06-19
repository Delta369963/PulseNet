"""FastAPI app — wiring only, no business logic (logic lives in services/).

Endpoints (called by the Next.js /api proxies):
  POST /ingest   — run feeds → consensus → ledger → shocks
  POST /ripple   — evaluate downstream exposure + reroutes for a shock
  GET  /ledger   — recent consensus-ledger rows (Responsible-AI panel)
  GET  /health   — feature flags + DB reachability (debugging aid)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import __version__
from app.config import get_settings
from app.db.session import get_engine
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
    description="Predictive decision-support engine — RSS ingestion, multi-agent "
    "Gemini consensus, SRI cascade math. Decision-support only; no autonomous execution.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def ripple(req: RippleRequest) -> RippleResponse:
    try:
        return ripple_service.evaluate_ripple(req.shockId)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        logger.exception("ripple evaluation failed")
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.get("/ledger", response_model=LedgerResponse)
def ledger(limit: int = 25) -> LedgerResponse:
    return ledger_service.recent_ledger(limit=limit)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
