"""Agent Gamma — Byzantine consensus judge.

Given Alpha's and Beta's structured extractions of the SAME raw item, Gamma:
  1. matches their events,
  2. computes a Byzantine agreement delta (0 = identical, 1 = total disagreement),
  3. emits the validated ConsensusShock (Alpha's view when they agree well, else
     the higher-confidence one, with a penalized confidence).

Pure deterministic math — no LLM. This makes consensus reproducible and testable.
"""

from __future__ import annotations

from app.schemas import ConsensusShock, StructuredShock

# Weights for the agreement-delta components (sum = 1).
_W_TYPE = 0.35
_W_SEVERITY = 0.25
_W_GEO = 0.20
_W_COUNTRIES = 0.20

_SEV_RANK = {"low": 0, "moderate": 1, "high": 2, "severe": 3}


def _severity_delta(a: str, b: str) -> float:
    return abs(_SEV_RANK.get(a, 1) - _SEV_RANK.get(b, 1)) / 3.0


def _geo_delta(a: StructuredShock, b: StructuredShock) -> float:
    """Normalized coordinate disagreement (0..1). Missing coords => neutral 0.5."""
    if a.lat is None or b.lat is None or a.lng is None or b.lng is None:
        return 0.5
    # Normalize by half-globe spans.
    dlat = abs(a.lat - b.lat) / 180.0
    dlng = abs(a.lng - b.lng) / 360.0
    return min(1.0, dlat + dlng)


def _country_delta(a: list[str], b: list[str]) -> float:
    """Jaccard distance between the two country-code sets."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return 1.0 - (inter / union if union else 0.0)


def agreement_delta(a: StructuredShock, b: StructuredShock) -> float:
    """Weighted Byzantine disagreement metric in [0, 1]."""
    type_delta = 0.0 if a.type == b.type else 1.0
    delta = (
        _W_TYPE * type_delta
        + _W_SEVERITY * _severity_delta(a.severity, b.severity)
        + _W_GEO * _geo_delta(a, b)
        + _W_COUNTRIES * _country_delta(a.country_codes, b.country_codes)
    )
    return round(min(1.0, max(0.0, delta)), 4)


def judge(
    alpha: StructuredShock,
    beta: StructuredShock | None,
    source_feed_url: str = "",
) -> ConsensusShock:
    """Reconcile Alpha + Beta into a validated ConsensusShock.

    If Beta is None (single-key / dark Beta), delta defaults to 0.5 (unverified)
    and Alpha's extraction is used as-is with a slight confidence penalty.
    """
    if beta is None:
        penalized = alpha.model_copy(update={"confidence": round(alpha.confidence * 0.9, 3)})
        return ConsensusShock(
            shock=penalized,
            byzantine_agreement_delta=0.5,
            alpha_raw=alpha.model_dump(),
            beta_raw={},
            source_feed_url=source_feed_url,
        )

    delta = agreement_delta(alpha, beta)
    # Pick the higher-confidence extraction as the canonical one.
    winner = alpha if alpha.confidence >= beta.confidence else beta
    # Penalize confidence proportionally to disagreement.
    adjusted = winner.model_copy(
        update={"confidence": round(winner.confidence * (1.0 - 0.5 * delta), 3)}
    )
    return ConsensusShock(
        shock=adjusted,
        byzantine_agreement_delta=delta,
        alpha_raw=alpha.model_dump(),
        beta_raw=beta.model_dump(),
        source_feed_url=source_feed_url,
    )
