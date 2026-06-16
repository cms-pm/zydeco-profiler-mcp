# SPDX-License-Identifier: MIT
"""Plain query/analytics API over a store path.

These functions carry no MCP dependency so they can be unit-tested directly and
reused by the CLI; ``mcp_server`` thin-wraps them as read-only tools.
"""
from __future__ import annotations

from pathlib import Path

from zydeco_profiler_mcp import db as _db
from zydeco_profiler_mcp.analytics.decision import decide_run, decision_to_dict
from zydeco_profiler_mcp.analytics.pareto import frontier_for_run
from zydeco_profiler_mcp.duck import run_readonly_query


def list_runs(db_path: str | Path) -> list[dict]:
    conn = _db.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, label, tool_version, created_at FROM runs ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def cells_summary(db_path: str | Path, run_id: int) -> list[dict]:
    conn = _db.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT c.name AS cell, c.is_baseline AS is_baseline,
                   m.name AS metric, SUM(meas.value) AS total
            FROM measurements meas
            JOIN cells c   ON c.id = meas.cell_id
            JOIN metrics m ON m.id = meas.metric_id
            WHERE meas.run_id = ?
            GROUP BY c.name, c.is_baseline, m.name
            ORDER BY c.name, m.name
            """,
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def pareto(db_path: str | Path, run_id: int, metrics: list[str]) -> dict:
    conn = _db.connect(db_path)
    try:
        return frontier_for_run(conn, run_id, metrics)
    finally:
        conn.close()


def decide(
    db_path: str | Path,
    run_id: int,
    baseline_cell: str,
    candidate_cell: str,
    margins: dict[str, float],
) -> dict:
    conn = _db.connect(db_path)
    try:
        decision = decide_run(
            conn,
            run_id,
            baseline_cell=baseline_cell,
            candidate_cell=candidate_cell,
            margins=margins,
        )
        return decision_to_dict(decision)
    finally:
        conn.close()


def sql(db_path: str | Path, query: str) -> list[dict]:
    return run_readonly_query(db_path, query)
