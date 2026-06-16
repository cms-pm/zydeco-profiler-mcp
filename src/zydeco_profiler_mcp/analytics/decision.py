# SPDX-License-Identifier: MIT
"""The pre-registered multi-objective decision rule (the Zydeco backbone).

A candidate regime beats the baseline only if it is **non-inferior** on every
gated metric (within a per-metric margin) **and** achieves at least one strict
win (better than the baseline beyond that margin). The rule is a pure function
so it can be frozen/pre-registered and replayed deterministically against
recorded evidence — no post-hoc tuning.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from zydeco_profiler_mcp.analytics.pareto import cell_points, metric_directions


@dataclass(frozen=True)
class MetricVerdict:
    metric: str
    baseline: float
    candidate: float
    ratio: float            # candidate / baseline (for lower_is_better metrics)
    margin: float
    non_inferior: bool
    strict_win: bool


@dataclass(frozen=True)
class Decision:
    verdict: str            # "go" | "no_go"
    candidate: str
    baseline: str
    reason: str
    metrics: list[MetricVerdict]


def apply_rule(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    margins: dict[str, float],
    lower_is_better: dict[str, float] | dict[str, bool],
    baseline_cell: str = "baseline",
    candidate_cell: str = "candidate",
) -> Decision:
    """Apply the non-inferior-on-all + strict-win-on-one rule.

    ``margins`` is a fractional tolerance per metric (e.g. 0.02 = 2%). For a
    lower-is-better metric: non-inferior iff candidate <= baseline*(1+margin);
    strict win iff candidate < baseline*(1-margin). Mirror-imaged for
    higher-is-better metrics.
    """
    verdicts: list[MetricVerdict] = []
    for metric in sorted(margins):
        base = float(baseline[metric])
        cand = float(candidate[metric])
        margin = float(margins[metric])
        lib = bool(lower_is_better[metric])
        ratio = (cand / base) if base != 0 else float("inf")
        if lib:
            non_inferior = cand <= base * (1.0 + margin)
            strict_win = cand < base * (1.0 - margin)
        else:
            non_inferior = cand >= base * (1.0 - margin)
            strict_win = cand > base * (1.0 + margin)
        verdicts.append(
            MetricVerdict(metric, base, cand, ratio, margin, non_inferior, strict_win)
        )

    all_non_inferior = all(v.non_inferior for v in verdicts)
    any_strict_win = any(v.strict_win for v in verdicts)
    go = all_non_inferior and any_strict_win

    if go:
        wins = [v.metric for v in verdicts if v.strict_win]
        reason = f"non-inferior on all gated metrics; strict win on {', '.join(wins)}"
    elif not all_non_inferior:
        regressions = [v.metric for v in verdicts if not v.non_inferior]
        reason = f"inferior beyond margin on {', '.join(regressions)}"
    else:
        reason = "non-inferior everywhere but no strict win beyond margin"

    return Decision(
        verdict="go" if go else "no_go",
        candidate=candidate_cell,
        baseline=baseline_cell,
        reason=reason,
        metrics=verdicts,
    )


def decide_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    baseline_cell: str,
    candidate_cell: str,
    margins: dict[str, float],
) -> Decision:
    """Pull aggregated (cell, metric) totals for a run and apply the rule."""
    metric_names = sorted(margins)
    directions = metric_directions(conn, metric_names)
    points = {p.cell: p.values for p in cell_points(conn, run_id, metric_names)}
    if baseline_cell not in points:
        raise ValueError(f"baseline cell not found: {baseline_cell}")
    if candidate_cell not in points:
        raise ValueError(f"candidate cell not found: {candidate_cell}")
    return apply_rule(
        points[baseline_cell],
        points[candidate_cell],
        margins=margins,
        lower_is_better=directions,
        baseline_cell=baseline_cell,
        candidate_cell=candidate_cell,
    )


def decision_to_dict(decision: Decision) -> dict[str, object]:
    return {
        "verdict": decision.verdict,
        "baseline": decision.baseline,
        "candidate": decision.candidate,
        "reason": decision.reason,
        "metrics": [
            {
                "metric": v.metric,
                "baseline": v.baseline,
                "candidate": v.candidate,
                "ratio": v.ratio,
                "margin": v.margin,
                "non_inferior": v.non_inferior,
                "strict_win": v.strict_win,
            }
            for v in decision.metrics
        ],
    }
