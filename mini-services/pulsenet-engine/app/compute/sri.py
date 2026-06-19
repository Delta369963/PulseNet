"""Sovereign Recuperation Index (SRI) — prompt §4.

SRI models a nation's capacity to stabilize after an infrastructural blow:

    SRI = w1 * gdp_norm + w2 * grid_density - w3 * historical_volatility

GDP per capita is log-normalized so high-income outliers (e.g. Qatar) don't
dwarf the scale. Output is clamped to [0.05, 1.0] so the cascade term
(1 - 1/SRI) stays finite. This mirrors `computeSri` in prisma/seed.ts exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Weights (must match prisma/seed.ts).
W1 = 0.5  # GDP per capita (normalized)
W2 = 0.3  # grid density
W3 = 0.2  # historical volatility

GDP_LOG_MIN = math.log(1000)   # ~poorest nation in catalog
GDP_LOG_MAX = math.log(80000)  # ~richest nation in catalog

SRI_FLOOR = 0.05
SRI_CEIL = 1.0


def normalize_gdp(gdp_per_capita: float) -> float:
    """Log-normalize GDP per capita into [0, 1]."""
    log_gdp = math.log(max(gdp_per_capita, 1.0))
    raw = (log_gdp - GDP_LOG_MIN) / (GDP_LOG_MAX - GDP_LOG_MIN)
    return min(1.0, max(0.0, raw))


def compute_sri(
    gdp_per_capita: float,
    grid_density: float,
    historical_volatility: float,
) -> float:
    """Compute the SRI, clamped to [0.05, 1.0] and rounded to 3 dp."""
    gdp_norm = normalize_gdp(gdp_per_capita)
    raw = W1 * gdp_norm + W2 * grid_density - W3 * historical_volatility
    clamped = min(SRI_CEIL, max(SRI_FLOOR, raw))
    return round(clamped, 3)


@dataclass(frozen=True)
class SriBreakdown:
    """Explainable SRI decomposition — every term is inspectable."""

    sri: float
    gdp_norm: float
    grid_term: float
    volatility_term: float


def sri_breakdown(
    gdp_per_capita: float,
    grid_density: float,
    historical_volatility: float,
) -> SriBreakdown:
    """Return the SRI plus its weighted component terms for interpretability."""
    gdp_norm = normalize_gdp(gdp_per_capita)
    return SriBreakdown(
        sri=compute_sri(gdp_per_capita, grid_density, historical_volatility),
        gdp_norm=round(gdp_norm, 3),
        grid_term=round(W2 * grid_density, 3),
        volatility_term=round(W3 * historical_volatility, 3),
    )
