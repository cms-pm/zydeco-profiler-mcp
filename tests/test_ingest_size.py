# SPDX-License-Identifier: MIT
from __future__ import annotations

from zydeco_profiler_mcp.ingest.size import ingest_size_report


def test_ingest_size_rows_and_values(conn, size_report):
    report = ingest_size_report(conn, size_report)
    assert report.rows == 6  # 3 cells x 2 metrics

    total = conn.execute("SELECT COUNT(*) AS n FROM measurements").fetchone()["n"]
    assert total == 6

    flash_c3 = conn.execute(
        """
        SELECT meas.value AS v FROM measurements meas
        JOIN cells c ON c.id = meas.cell_id
        JOIN metrics m ON m.id = meas.metric_id
        WHERE c.name = 'cell3_cpp_custom' AND m.name = 'flash_bytes'
        """
    ).fetchone()["v"]
    assert flash_c3 == 5200.0

    baseline = conn.execute(
        "SELECT name FROM cells WHERE is_baseline = 1"
    ).fetchone()["name"]
    assert baseline == "cell1_c_hal"


def test_ingest_is_idempotent(conn, size_report):
    ingest_size_report(conn, size_report)
    ingest_size_report(conn, size_report)  # second ingest must converge
    total = conn.execute("SELECT COUNT(*) AS n FROM measurements").fetchone()["n"]
    runs = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
    assert total == 6
    assert runs == 1
