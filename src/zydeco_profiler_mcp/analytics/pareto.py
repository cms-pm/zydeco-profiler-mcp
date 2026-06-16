# SPDX-License-Identifier: MIT
"""Multi-objective Pareto analytics over the benchmark matrix.

Aggregates measurements to one value per (cell, metric) and computes the
non-dominated frontier, respecting each metric's ``lower_is_better`` flag. This
is the analytical backbone of the "size AND cycles, both gated" decision: the
winning regime must sit on (or beat) the frontier.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class CellPoint:
    cell: str
    is_baseline: bool
    values: dict[str, float]      # metric name -> aggregated value


def metric_directions(conn: sqlite3.Connection, metric_names: list[str]) -> dict[str, bool]:
    """metric name -> lower_is_better (True/False)."""
    out: dict[str, bool] = {}
    for name in metric_names:
        row = conn.execute(
            "SELECT lower_is_better FROM metrics WHERE name = ?", (name,)
        ).fetchone()
        out[name] = bool(row["lower_is_better"]) if row is not None else True
    return out


def cell_points(
    conn: sqlite3.Connection, run_id: int, metric_names: list[str]
) -> list[CellPoint]:
    """One CellPoint per cell, each metric aggregated as SUM(value) over regions."""
    placeholders = ",".join("?" for _ in metric_names)
    rows = conn.execute(
        f"""
        SELECT c.name AS cell, c.is_baseline AS is_baseline,
               m.name AS metric, SUM(meas.value) AS total
        FROM measurements meas
        JOIN cells c   ON c.id = meas.cell_id
        JOIN metrics m ON m.id = meas.metric_id
        WHERE meas.run_id = ? AND m.name IN ({placeholders})
        GROUP BY c.name, c.is_baseline, m.name
        """,
        (run_id, *metric_names),
    ).fetchall()
    grouped: dict[str, dict[str, float]] = {}
    baseline: dict[str, bool] = {}
    for row in rows:
        grouped.setdefault(row["cell"], {})[row["metric"]] = float(row["total"])
        baseline[row["cell"]] = bool(row["is_baseline"])
    return [
        CellPoint(cell=cell, is_baseline=baseline[cell], values=values)
        for cell, values in sorted(grouped.items())
    ]


def _dominates(a: dict[str, float], b: dict[str, float], lower_is_better: dict[str, bool]) -> bool:
    """True if a dominates b: at-least-as-good on every metric, strictly better on one."""
    strictly_better_somewhere = False
    for metric, lib in lower_is_better.items():
        av, bv = a[metric], b[metric]
        better = av <= bv if lib else av >= bv
        strictly = av < bv if lib else av > bv
        if not better:
            return False
        if strictly:
            strictly_better_somewhere = True
    return strictly_better_somewhere


def pareto_frontier(
    points: list[CellPoint], lower_is_better: dict[str, bool]
) -> list[CellPoint]:
    """Return the non-dominated subset of ``points``."""
    frontier: list[CellPoint] = []
    for p in points:
        dominated = any(
            _dominates(other.values, p.values, lower_is_better)
            for other in points
            if other.cell != p.cell
        )
        if not dominated:
            frontier.append(p)
    return frontier


def frontier_for_run(
    conn: sqlite3.Connection, run_id: int, metric_names: list[str]
) -> dict[str, object]:
    """Convenience: points + frontier + directions for a run, as plain dicts."""
    directions = metric_directions(conn, metric_names)
    points = cell_points(conn, run_id, metric_names)
    frontier = pareto_frontier(points, directions)
    return {
        "run_id": run_id,
        "metrics": metric_names,
        "lower_is_better": directions,
        "points": [{"cell": p.cell, "is_baseline": p.is_baseline, **p.values} for p in points],
        "frontier": sorted(p.cell for p in frontier),
    }
