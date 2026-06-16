# SPDX-License-Identifier: MIT
"""Natural-key upsert helpers shared by ingesters.

Every helper is idempotent: re-ingesting the same evidence converges to the
same rows (determinism + idempotency are first-class, mirroring eval-grading).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_PROVENANCE_COLS = (
    "compiler_version",
    "target_flags",
    "toolchain_commit",
    "elf_sha256",
    "map_sha256",
    "size_sha256",
    "board_id",
    "probe_serial",
    "scope_device",
    "bracket_overhead_cycles",
)


@dataclass(frozen=True)
class CountReport:
    rows: int


def get_or_create_run(
    conn: sqlite3.Connection, label: str, *, created_at: str, tool_version: str | None = None
) -> int:
    conn.execute(
        "INSERT INTO runs(label, tool_version, created_at) VALUES(?, ?, ?) "
        "ON CONFLICT(label) DO NOTHING",
        (label, tool_version, created_at),
    )
    return int(conn.execute("SELECT id FROM runs WHERE label = ?", (label,)).fetchone()["id"])


def set_provenance(conn: sqlite3.Connection, run_id: int, provenance: dict[str, object]) -> None:
    cols = [c for c in _PROVENANCE_COLS if c in provenance]
    if not cols:
        conn.execute("INSERT OR IGNORE INTO run_provenance(run_id) VALUES(?)", (run_id,))
        return
    assignments = ", ".join(f"{c}=excluded.{c}" for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(
        f"INSERT INTO run_provenance(run_id, {', '.join(cols)}) "
        f"VALUES(?, {placeholders}) "
        f"ON CONFLICT(run_id) DO UPDATE SET {assignments}",
        (run_id, *(provenance[c] for c in cols)),
    )


def get_or_create_cell(
    conn: sqlite3.Connection,
    run_id: int,
    name: str,
    *,
    language: str | None = None,
    drivers: str | None = None,
    is_baseline: bool = False,
) -> int:
    conn.execute(
        "INSERT INTO cells(run_id, name, language, drivers, is_baseline) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, name) DO UPDATE SET "
        "language=excluded.language, drivers=excluded.drivers, is_baseline=excluded.is_baseline",
        (run_id, name, language, drivers, 1 if is_baseline else 0),
    )
    return int(
        conn.execute(
            "SELECT id FROM cells WHERE run_id = ? AND name = ?", (run_id, name)
        ).fetchone()["id"]
    )


def get_or_create_region(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT INTO regions(name) VALUES(?) ON CONFLICT(name) DO NOTHING", (name,))
    return int(conn.execute("SELECT id FROM regions WHERE name = ?", (name,)).fetchone()["id"])


def get_or_create_metric(
    conn: sqlite3.Connection, name: str, *, unit: str | None = None, lower_is_better: bool = True
) -> int:
    conn.execute(
        "INSERT INTO metrics(name, unit, lower_is_better) VALUES(?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET unit=excluded.unit, lower_is_better=excluded.lower_is_better",
        (name, unit, 1 if lower_is_better else 0),
    )
    return int(conn.execute("SELECT id FROM metrics WHERE name = ?", (name,)).fetchone()["id"])


def upsert_measurement(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    cell_id: int,
    region_id: int,
    metric_id: int,
    value: float,
    p50: float | None = None,
    p99: float | None = None,
    p999: float | None = None,
    sample_count: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO measurements"
        "(run_id, cell_id, region_id, metric_id, value, p50, p99, p999, sample_count) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, cell_id, region_id, metric_id) DO UPDATE SET "
        "value=excluded.value, p50=excluded.p50, p99=excluded.p99, p999=excluded.p999, "
        "sample_count=excluded.sample_count",
        (run_id, cell_id, region_id, metric_id, value, p50, p99, p999, sample_count),
    )
