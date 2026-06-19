"""Monte Carlo shortage-window simulation (deterministic under a fixed seed).

Models: a reroute's supply arrives at time-to-add (TTA); the shortage begins at
time-to-shortage (TTS). Both are noisy. The shortage window = max(0, TTA - TTS).
Success = reroute arrives before the shortage bites (TTA <= TTS).

Mirrors the TypeScript `monteCarlo` in src/lib/pulsenet/ripple.ts, but uses numpy
for vectorized speed and a seeded RNG so unit tests get stable numbers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class MonteCarloOutcome:
    trials: int
    medianShortageWindow: float
    p95ShortageWindow: float
    successProb: float

    def to_dict(self) -> dict:
        return asdict(self)


def monte_carlo(
    tts_days: float,
    tta_days: float,
    trials: int = 4000,
    seed: int | None = None,
) -> MonteCarloOutcome:
    """Run the shortage-window simulation.

    Args:
        tts_days: estimated days until the shortage materializes.
        tta_days: estimated days to add the alternative supply (reroute).
        trials: number of Monte Carlo trials.
        seed: optional RNG seed for reproducible results (tests pass a seed).
    """
    rng = np.random.default_rng(seed)
    # TTA noise: wider (logistics uncertainty). TTS noise: narrower.
    tta = np.maximum(1.0, tta_days * (0.75 + 0.5 * rng.standard_normal(trials)))
    tts = np.maximum(1.0, tts_days * (0.90 + 0.25 * rng.standard_normal(trials)))
    windows = np.maximum(0.0, tta - tts)
    success_prob = float(np.mean(tta <= tts))
    return MonteCarloOutcome(
        trials=trials,
        medianShortageWindow=round(float(np.percentile(windows, 50)), 1),
        p95ShortageWindow=round(float(np.percentile(windows, 95)), 1),
        successProb=round(success_prob, 2),
    )
