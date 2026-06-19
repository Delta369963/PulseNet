"""Unit tests for Agent Gamma's Byzantine consensus math."""

from app.agents.gamma import agreement_delta, judge
from app.schemas import StructuredShock


def _shock(**kw) -> StructuredShock:
    base = dict(
        title="Port closure",
        description="desc",
        type="port_closure",
        severity="high",
        severity_score=7,
        location_name="Black Sea",
        lat=46.5,
        lng=32.0,
        country_codes=["RUS", "UKR"],
        confidence=0.8,
    )
    base.update(kw)
    return StructuredShock(**base)


def test_identical_extractions_zero_delta():
    a = _shock()
    b = _shock()
    assert agreement_delta(a, b) == 0.0


def test_total_disagreement_high_delta():
    a = _shock(type="port_closure", severity="severe", country_codes=["RUS"], lat=46, lng=32)
    b = _shock(type="earthquake", severity="low", country_codes=["JPN"], lat=-40, lng=170)
    assert agreement_delta(a, b) > 0.6


def test_judge_penalizes_confidence_on_disagreement():
    a = _shock(confidence=0.9)
    b = _shock(type="conflict", severity="low", confidence=0.6)
    result = judge(a, b)
    # Winner is alpha (higher confidence) but penalized by the delta.
    assert result.shock.confidence < 0.9
    assert result.byzantine_agreement_delta > 0
    assert result.alpha_raw and result.beta_raw


def test_judge_single_key_marks_unverified():
    a = _shock()
    result = judge(a, None, source_feed_url="https://x")
    assert result.byzantine_agreement_delta == 0.5
    assert result.beta_raw == {}
    assert result.source_feed_url == "https://x"
