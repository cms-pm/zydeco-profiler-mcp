# SPDX-License-Identifier: MIT
"""SQLite connection + idempotent migration runner.

Ported from the eval-grading infrastructure and made package-local: schema
lives inside the package (``zydeco_profiler_mcp/schema``) so dev and installed
runs resolve identically via importlib.resources. ``migrate`` re-runs every
script, so all schema is ``CREATE ... IF NOT EXISTS`` and ingest upserts.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator


def migration_texts() -> list[tuple[str, str]]:
    """Return ``(name, sql)`` pairs sorted by filename."""
    schema = files("zydeco_profiler_mcp").joinpath("schema")
    items = [
        (entry.name, entry.read_text(encoding="utf-8"))
        for entry in schema.iterdir()
        if entry.name.endswith(".sql")
    ]
    return sorted(items, key=lambda item: item[0])


def connect(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    for _name, sql in migration_texts():
        conn.executescript(sql)
    conn.commit()


@contextmanager
def txn(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        conn.execute("BEGIN")
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
