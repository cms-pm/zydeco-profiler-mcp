# SPDX-License-Identifier: MIT
"""Read-only DuckDB SQL surface over the SQLite store.

Ported from eval-grading. The write-guard makes the ``sql`` MCP tool safe to
expose to agents: only read queries reach the attached database, which is also
opened ``READ_ONLY``.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

WRITE_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|COPY|REPLACE|PRAGMA)\b",
    re.I,
)


def connect_readonly(sqlite_path: str | Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute("PRAGMA threads=1")
    escaped = str(Path(sqlite_path)).replace("'", "''")
    conn.execute(f"ATTACH '{escaped}' AS z (TYPE SQLITE, READ_ONLY)")
    conn.execute("USE z")
    return conn


def run_readonly_query(sqlite_path: str | Path, query: str) -> list[dict]:
    if WRITE_RE.search(query):
        raise ValueError("sql query must be read-only")
    conn = connect_readonly(sqlite_path)
    try:
        result = conn.execute(query)
        columns = [item[0] for item in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        conn.close()
