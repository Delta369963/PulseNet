"""Monte Carlo simulation for reroute success probability."""

import numpy as np
from typing import Dict, List


def simulate_reroute(
    base_delay_days: float,
    base_success_prob: float,
    n_simulations: int = 500,
    disruption_severity: float = 0.5,
) -> Dict:
    """
    Quick Monte Carlo on a reroute alternative.
    disruption_severity: 0-1, higher = worse original shock
    """
    rng = np.random.default_rng(42)

    delay_samples = rng.normal(base_delay_days, base_delay_days * 0.25, n_simulations)
    delay_samples = np.clip(delay_samples, 1, base_delay_days * 3)

    success_samples = rng.binomial(1, base_success_prob, n_simulations)
    # Worse disruption reduces success probability
    adjusted_success = success_samples * (1 - disruption_severity * 0.3)
    success_rate = float(np.mean(adjusted_success))

    return {
        "estimated_delay_days": float(np.median(delay_samples)),
        "delay_std": float(np.std(delay_samples)),
        "success_probability": round(success_rate, 3),
        "confidence": round(min(0.95, 0.5 + success_rate * 0.4), 3),
        "simulations_run": n_simulations,
    }


def rank_alternatives(alternatives: List[Dict], disruption_severity: float = 0.5) -> List[Dict]:
    """Run Monte Carlo on each alternative and rank by success probability."""
    ranked = []
    for alt in alternatives:
        sim = simulate_reroute(
            alt.get("base_delay_days", 14),
            alt.get("base_success_prob", 0.6),
            disruption_severity=disruption_severity,
        )
        ranked.append({**alt, **sim})

    ranked.sort(key=lambda x: (-x["success_probability"], x["estimated_delay_days"]))
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return ranked
