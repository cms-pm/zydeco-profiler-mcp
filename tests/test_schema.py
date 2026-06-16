# SPDX-License-Identifier: MIT
"""Schema-level normalization and integrity invariants."""
from __future__ import annotations

import sqlite3

import pytest

from zydeco_profiler_mcp import db as _db
from zydeco_profiler_mcp.ingest.cycles import ingest_cycle_report


def _cols(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_measurements_has_no_run_id(conn):
    # run_id is reached via cell_id -> cells.run_id; storing it would be a
    # partial-key (2NF) dependency. It must not exist on the fact table.
    cols = _cols(conn, "measurements")
    assert "run_id" not in cols
    assert {"cell_id", "region_id", "metric_id", "value"} <= cols


def test_measurements_natural_key_is_cell_region_metric(conn, cycle_report):
    ingest_cycle_report(conn, cycle_report)
    # The UNIQUE(cell_id, region_id, metric_id) constraint must reject a
    # duplicate fact for the same coordinates.
    row = conn.execute(
        "SELECT cell_id, region_id, metric_id FROM measurements LIMIT 1"
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO measurements(cell_id, region_id, metric_id, value) "
            "VALUES(?, ?, ?, ?)",
            (row["cell_id"], row["region_id"], row["metric_id"], 1.0),
        )


def test_one_baseline_per_run_enforced(conn):
    run_id = conn.execute(
        "INSERT INTO runs(label, created_at) VALUES('r', '2026-01-01') RETURNING id"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO cells(run_id, name, is_baseline) VALUES(?, 'a', 1)", (run_id,)
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cells(run_id, name, is_baseline) VALUES(?, 'b', 1)", (run_id,)
        )
    # A non-baseline second cell in the same run is fine.
    conn.execute(
        "INSERT INTO cells(run_id, name, is_baseline) VALUES(?, 'c', 0)", (run_id,)
    )


def test_run_scoping_resolves_through_cells(db_path, cycle_report):
    # Two separate runs must not bleed into each other even though measurements
    # no longer carry run_id directly.
    conn = _db.connect(db_path)
    _db.migrate(conn)
    ingest_cycle_report(conn, cycle_report)
    ingest_cycle_report(conn, {**cycle_report, "run": "second-run"})

    run_ids = [r["id"] for r in conn.execute("SELECT id FROM runs ORDER BY id").fetchall()]
    assert len(run_ids) == 2
    for rid in run_ids:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM measurements meas "
            "JOIN cells c ON c.id = meas.cell_id WHERE c.run_id = ?",
            (rid,),
        ).fetchone()["n"]
        assert n == 4  # 2 cells x (cycles + cycles_dwt), no derived xcheck row
    conn.close()
