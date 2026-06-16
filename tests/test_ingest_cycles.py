# SPDX-License-Identifier: MIT
from __future__ import annotations

import copy

import pytest

from zydeco_profiler_mcp.ingest.cycles import ingest_cycle_report


def _measurement(conn, cell, region, metric):
    row = conn.execute(
        """
        SELECT meas.value AS value, meas.p50 AS p50, meas.p99 AS p99,
               meas.p999 AS p999, meas.sample_count AS n
        FROM measurements meas
        JOIN cells c ON c.id = meas.cell_id
        JOIN regions r ON r.id = meas.region_id
        JOIN metrics m ON m.id = meas.metric_id
        WHERE c.name = ? AND r.name = ? AND m.name = ?
        """,
        (cell, region, metric),
    ).fetchone()
    return row


def test_scope_overhead_subtracted_and_percentiles(conn, cycle_report):
    ingest_cycle_report(conn, cycle_report)

    # cell1 scope: [212,213,211,212,214] - 12 overhead -> median 200
    c1 = _measurement(conn, "cell1_c_hal", "uart_tx", "cycles")
    assert c1["value"] == 200.0
    assert c1["p50"] == 200.0
    assert c1["n"] == 5

    # cell3 is faster: median 180
    c3 = _measurement(conn, "cell3_cpp_custom", "uart_tx", "cycles")
    assert c3["value"] == 180.0


def test_dwt_recorded_and_xcheck_within_tolerance(conn, cycle_report):
    result = ingest_cycle_report(conn, cycle_report)

    dwt = _measurement(conn, "cell1_c_hal", "uart_tx", "cycles_dwt")
    assert dwt["value"] == 201.0  # no bracket subtract on dwt by default

    xrow = _measurement(conn, "cell1_c_hal", "uart_tx", "cycles_xcheck_rel_error")
    assert xrow is not None
    assert xrow["value"] == pytest.approx(abs(200.0 - 201.0) / 201.0)

    assert result.out_of_tolerance == ()
    assert all(x.within_tolerance for x in result.xchecks)


def test_out_of_tolerance_flagged(conn, cycle_report):
    bad = copy.deepcopy(cycle_report)
    # Make the scope read wildly off from DWT for cell1.
    bad["cells"][0]["regions"][0]["dwt_cycles"] = [100, 100, 100, 100, 100]
    result = ingest_cycle_report(conn, bad)

    assert len(result.out_of_tolerance) == 1
    flagged = result.out_of_tolerance[0]
    assert flagged.cell == "cell1_c_hal"
    assert flagged.within_tolerance is False
    assert flagged.rel_error > 0.05


def test_scope_cycles_passthrough_and_no_dwt(conn):
    report = {
        "run": "cycles-passthrough",
        "clock_hz": 170_000_000,
        "cells": [
            {
                "name": "cellX",
                "is_baseline": True,
                "regions": [{"region": "fsm_step", "scope_cycles": [50, 51, 49, 50, 50]}],
            }
        ],
    }
    result = ingest_cycle_report(conn, report)
    row = _measurement(conn, "cellX", "fsm_step", "cycles")
    assert row["value"] == 50.0
    # No DWT -> no cross-check rows, xcheck recorded as None.
    assert _measurement(conn, "cellX", "fsm_step", "cycles_dwt") is None
    assert result.xchecks[0].dwt_p50 is None
    assert result.xchecks[0].within_tolerance is None


def test_ingest_is_idempotent(conn, cycle_report):
    ingest_cycle_report(conn, cycle_report)
    first = conn.execute("SELECT COUNT(*) AS n FROM measurements").fetchone()["n"]
    ingest_cycle_report(conn, cycle_report)
    second = conn.execute("SELECT COUNT(*) AS n FROM measurements").fetchone()["n"]
    runs = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
    assert first == second
    assert runs == 1


def test_decision_consumes_cycles_metric(conn, cycle_report):
    from zydeco_profiler_mcp.analytics.decision import decide_run

    ingest_cycle_report(conn, cycle_report)
    run_id = conn.execute("SELECT id FROM runs").fetchone()["id"]
    decision = decide_run(
        conn,
        run_id,
        baseline_cell="cell1_c_hal",
        candidate_cell="cell3_cpp_custom",
        margins={"cycles": 0.05},
    )
    # cell3 200->180 is a ~10% strict win, well past the 5% margin.
    assert decision.verdict == "go"
