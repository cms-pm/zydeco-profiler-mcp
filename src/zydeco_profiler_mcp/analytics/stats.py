# SPDX-License-Identifier: MIT
"""Statistical-rigor helpers (ported from eval-grading).

Pure functions, no DB or I/O. Bootstrap resampling is deterministic given a
fixed seed so emitted tables are reproducible. Used for confidence intervals on
size/cycle deltas and percentile summaries of cycle distributions.
"""
from __future__ import annotations

from random import Random
from statistics import NormalDist


def percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile on an already-sorted list."""
    if not sorted_values:
        raise ValueError("empty input")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def percentiles(values: list[float]) -> dict[str, float] | None:
    """p50/p99/p999 (and min/max) for a sample, or None when empty."""
    if not values:
        return None
    s = sorted(float(v) for v in values)
    return {
        "min": s[0],
        "p50": percentile(s, 0.50),
        "p99": percentile(s, 0.99),
        "p999": percentile(s, 0.999),
        "max": s[-1],
    }


def bootstrap_ci(
    values: list[float],
    *,
    confidence: float = 0.95,
    resamples: int = 1000,
    seed: int = 0,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for the mean of ``values``. Deterministic per seed."""
    if not values:
        return None
    n = len(values)
    if n == 1:
        return (float(values[0]), float(values[0]))
    rng = Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = 1.0 - confidence
    return (percentile(means, alpha / 2.0), percentile(means, 1.0 - alpha / 2.0))


def wilson_ci(
    successes: int, n: int, *, confidence: float = 0.95
) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion. None when n == 0."""
    if n <= 0:
        return None
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    p_hat = successes / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    margin = (z / denom) * ((p_hat * (1.0 - p_hat) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, center - margin), min(1.0, center + margin))
