# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from zydeco_profiler_mcp import api
from zydeco_profiler_mcp import db as _db
from zydeco_profiler_mcp.duck import run_readonly_query
from zydeco_profiler_mcp.ingest.size import ingest_size_report


def _seed(db_path, report):
    conn = _db.connect(db_path)
    _db.migrate(conn)
    ingest_size_report(conn, report)
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


def test_readonly_guard_blocks_writes(db_path, size_report):
    _seed(db_path, size_report)
    rows = run_readonly_query(db_path, "SELECT COUNT(*) AS n FROM measurements")
    assert rows[0]["n"] == 6
    with pytest.raises(ValueError):
        run_readonly_query(db_path, "DELETE FROM measurements")
