"""Ledger service — reads the consensus ledger for the Responsible-AI panel."""

from __future__ import annotations

import json

from app.db import repo
from app.db.session import session_scope
from app.schemas import LedgerResponse, LedgerRow


def recent_ledger(limit: int = 25) -> LedgerResponse:
    """Return the most recent consensus-ledger rows (newest first)."""
    with session_scope() as s:
        rows = repo.recent_ledger(s, limit=limit)
        out: list[LedgerRow] = []
        for r in rows:
            try:
                vector = json.loads(r.detectedShockVector)
            except (json.JSONDecodeError, TypeError):
                vector = {}
            ts = r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else str(r.timestamp)
            out.append(
                LedgerRow(
                    crisisId=r.crisisId,
                    timestamp=ts,
                    shockId=r.shockId,
                    sourceFeedUrl=r.sourceFeedUrl,
                    detectedShockVector=vector,
                    byzantineAgreementDelta=r.byzantineAgreementDelta,
                    humanInTheLoopOverride=bool(r.humanInTheLoopOverride),
                    authorizedByAdmin=r.authorizedByAdmin,
                )
            )
    return LedgerResponse(ledger=out)
