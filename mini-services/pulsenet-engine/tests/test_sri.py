"""Unit tests for the Sovereign Recuperation Index."""

from app.compute.sri import compute_sri, normalize_gdp, sri_breakdown


def test_normalize_gdp_bounds():
    assert normalize_gdp(1) == 0.0  # below floor clamps to 0
    assert 0.0 <= normalize_gdp(2480) <= 1.0
    assert normalize_gdp(1_000_000) == 1.0  # above ceiling clamps to 1


def test_compute_sri_clamped_range():
    # Very poor + fragile nation: clamped to the floor, never below.
    low = compute_sri(gdp_per_capita=900, grid_density=0.1, historical_volatility=0.95)
    assert low >= 0.05
    # Wealthy + stable nation: high but never above 1.
    high = compute_sri(gdp_per_capita=80000, grid_density=0.96, historical_volatility=0.1)
    assert high <= 1.0
    assert high > low


def test_compute_sri_matches_seed_formula():
    # Mirror prisma/seed.ts computeSri for India's inputs.
    # 0.5*0.207 + 0.3*0.62 - 0.2*0.45 ≈ 0.20
    sri = compute_sri(2480, 0.62, 0.45)
    assert sri == 0.2



def test_higher_volatility_lowers_sri():
    stable = compute_sri(20000, 0.8, 0.2)
    volatile = compute_sri(20000, 0.8, 0.9)
    assert stable > volatile


def test_breakdown_components_sum_consistently():
    b = sri_breakdown(20000, 0.8, 0.3)
    assert 0.0 <= b.gdp_norm <= 1.0
    assert b.grid_term == round(0.3 * 0.8, 3)
    assert b.volatility_term == round(0.2 * 0.3, 3)
    assert b.sri == compute_sri(20000, 0.8, 0.3)
