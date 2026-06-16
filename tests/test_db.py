# SPDX-License-Identifier: MIT
from __future__ import annotations

from zydeco_profiler_mcp import db as _db


def test_migrate_is_idempotent(db_path):
    conn = _db.connect(db_path)
    _db.migrate(conn)
    _db.migrate(conn)  # re-run must not raise
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"runs", "run_provenance", "cells", "regions", "metrics", "measurements"} <= tables
