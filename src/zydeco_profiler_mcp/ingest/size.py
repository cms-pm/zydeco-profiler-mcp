# SPDX-License-Identifier: MIT
"""Ingest a code-size report (SiL stage) into the benchmark store.

Report shape (project-neutral)::

    {
      "run": "zydeco-9.4.9.1-size",
      "tool_version": "0.1.0",
      "provenance": {"compiler_version": "...", "target_flags": "...",
                     "elf_sha256": "...", "map_sha256": "...", "size_sha256": "..."},
      "metrics": [{"name": "flash_bytes", "unit": "bytes", "lower_is_better": true},
                  {"name": "sram_bytes",  "unit": "bytes", "lower_is_better": true}],
      "cells": [
        {"name": "cell1_c_hal", "language": "c11", "drivers": "hal",
         "is_baseline": true,
         "measurements": [{"region": "whole_image", "metric": "flash_bytes", "value": 5348},
                          {"region": "whole_image", "metric": "sram_bytes",  "value": 4}]}
      ]
    }

Idempotent: re-ingesting the same report converges to the same rows.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from zydeco_profiler_mcp.ingest.common import (
    CountReport,
    get_or_create_cell,
    get_or_create_metric,
    get_or_create_region,
    get_or_create_run,
    set_provenance,
    upsert_measurement,
)


def ingest_size_report(conn: sqlite3.Connection, report: dict) -> CountReport:
    label = report["run"]
    created_at = report.get("created_at") or datetime.now(UTC).isoformat()
    run_id = get_or_create_run(
        conn, label, created_at=created_at, tool_version=report.get("tool_version")
    )
    set_provenance(conn, run_id, report.get("provenance", {}))

    metric_meta = {m["name"]: m for m in report.get("metrics", [])}
    metric_ids: dict[str, int] = {}
    for name, meta in metric_meta.items():
        metric_ids[name] = get_or_create_metric(
            conn, name, unit=meta.get("unit"), lower_is_better=meta.get("lower_is_better", True)
        )

    rows = 0
    for cell in report["cells"]:
        cell_id = get_or_create_cell(
            conn,
            run_id,
            cell["name"],
            language=cell.get("language"),
            drivers=cell.get("drivers"),
            is_baseline=bool(cell.get("is_baseline", False)),
        )
        for meas in cell.get("measurements", []):
            metric_name = meas["metric"]
            if metric_name not in metric_ids:
                metric_ids[metric_name] = get_or_create_metric(conn, metric_name)
            region_id = get_or_create_region(conn, meas["region"])
            upsert_measurement(
                conn,
                run_id=run_id,
                cell_id=cell_id,
                region_id=region_id,
                metric_id=metric_ids[metric_name],
                value=float(meas["value"]),
                sample_count=int(meas.get("sample_count", 1)),
            )
            rows += 1
    conn.commit()
    return CountReport(rows=rows)
