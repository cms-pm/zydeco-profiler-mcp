# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from zydeco_profiler_mcp import api
from zydeco_profiler_mcp import db as _db
from zydeco_profiler_mcp.duck import run_readonly_query
from zydeco_profiler_mcp.ingest.cycles import ingest_cycle_report
from zydeco_profiler_mcp.ingest.size import ingest_size_report


def _seed(db_path, report):
    conn = _db.connect(db_path)
    _db.migrate(conn)
    ingest_size_report(conn, report)
    conn.close()


def _seed_cycles(db_path, report):
    conn = _db.connect(db_path)
    _db.migrate(conn)
    ingest_cycle_report(conn, report)
    conn.close()


def test_api_end_to_end(db_path, size_report):
    _seed(db_path, size_report)

    runs = api.list_runs(db_path)
    assert len(runs) == 1
    run_id = runs[0]["id"]

    frontier = api.pareto(db_path, run_id, ["flash_bytes", "sram_bytes"])
    assert frontier["frontier"] == ["cell3_cpp_custom"]

    decision = api.decide(
        db_path,
        run_id,
        "cell1_c_hal",
        "cell3_cpp_custom",
        {"flash_bytes": 0.02, "sram_bytes": 0.02},
    )
    assert decision["verdict"] == "go"


def test_xchecks_passes_within_tolerance(db_path, cycle_report):
    _seed_cycles(db_path, cycle_report)
    result = api.xchecks(db_path, 1)
    assert result["out_of_tolerance"] == []
    assert len(result["checks"]) == 2
    c1 = next(c for c in result["checks"] if c["cell"] == "cell1_c_hal")
    assert c1["scope_p50"] == 200.0
    assert c1["dwt_p50"] == 201.0
    assert c1["within_tolerance"] is True


def test_xchecks_tightening_tolerance_flags(db_path, cycle_report):
    _seed_cycles(db_path, cycle_report)
    # rel_error ~0.005; a 0.001 tolerance must flag both regions at query time
    # without re-ingesting.
    result = api.xchecks(db_path, 1, tolerance=0.001)
    assert len(result["out_of_tolerance"]) == 2


def test_readonly_guard_blocks_writes(db_path, size_report):
    _seed(db_path, size_report)
    rows = run_readonly_query(db_path, "SELECT COUNT(*) AS n FROM measurements")
    assert rows[0]["n"] == 6
    with pytest.raises(ValueError):
        run_readonly_query(db_path, "DELETE FROM measurements")
