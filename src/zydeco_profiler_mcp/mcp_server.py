# SPDX-License-Identifier: MIT
"""Read-only MCP surface (FastMCP, stdio).

Thin wrappers over ``api`` so agents can query the benchmark store, compute the
Pareto frontier, and apply the pre-registered decision rule — without any write
path. The store location comes from the ``ZYDECO_PROFILER_DB`` env var or a
per-call ``db_path`` override.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from zydeco_profiler_mcp import api

mcp = FastMCP("zydeco-profiler-mcp")


def _db(db_path: str) -> str:
    return db_path or os.environ.get("ZYDECO_PROFILER_DB", "zydeco.db")


@mcp.tool()
def list_runs(db_path: str = "") -> list[dict]:
    """List measurement runs (campaigns) in the store."""
    return api.list_runs(_db(db_path))


@mcp.tool()
def cells_summary(run_id: int, db_path: str = "") -> list[dict]:
    """Per-cell, per-metric totals for a run."""
    return api.cells_summary(_db(db_path), run_id)


@mcp.tool()
def pareto(run_id: int, metrics: list[str], db_path: str = "") -> dict:
    """Pareto frontier over the given metrics for a run (lower_is_better aware)."""
    return api.pareto(_db(db_path), run_id, metrics)


@mcp.tool()
def decide(
    run_id: int,
    baseline_cell: str,
    candidate_cell: str,
    margins: dict[str, float],
    db_path: str = "",
) -> dict:
    """Apply the pre-registered non-inferior+strict-win rule to a candidate cell."""
    return api.decide(_db(db_path), run_id, baseline_cell, candidate_cell, margins)


@mcp.tool()
def xchecks(run_id: int, tolerance: float = 0.05, db_path: str = "") -> dict:
    """Scope-vs-DWT cycle cross-check per (cell, region), re-screened at tolerance."""
    return api.xchecks(_db(db_path), run_id, tolerance)


@mcp.tool()
def query(sql: str, db_path: str = "") -> list[dict]:
    """Run a read-only SQL query against the store (writes are rejected)."""
    return api.sql(_db(db_path), sql)


def run_stdio() -> None:
    mcp.run()
