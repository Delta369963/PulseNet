"""Unit tests for the Monte Carlo shortage-window simulation."""

from app.compute.monte_carlo import monte_carlo


def test_seeded_run_is_deterministic():
    a = monte_carlo(tts_days=10, tta_days=8, trials=2000, seed=42)
    b = monte_carlo(tts_days=10, tta_days=8, trials=2000, seed=42)
    assert a.to_dict() == b.to_dict()


def test_fast_reroute_has_high_success():
    # Reroute arrives well before the shortage => high success probability.
    out = monte_carlo(tts_days=20, tta_days=3, trials=4000, seed=1)
    assert out.successProb > 0.8


def test_slow_reroute_has_low_success():
    # Reroute much slower than shortage onset => low success probability.
    out = monte_carlo(tts_days=3, tta_days=25, trials=4000, seed=1)
    assert out.successProb < 0.2


def test_p95_not_less_than_median():
    out = monte_carlo(tts_days=8, tta_days=10, trials=4000, seed=7)
    assert out.p95ShortageWindow >= out.medianShortageWindow
    assert out.trials == 4000
