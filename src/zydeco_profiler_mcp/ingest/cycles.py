# SPDX-License-Identifier: MIT
"""Ingest an on-target cycle report (HIL stage) into the benchmark store.

Cycle evidence is a *distribution*, not a single number. Each region carries
raw samples from the external WaveForms scope (bracket-pin pulse widths) and,
optionally, corroborating Brontes DWT cycle counts. This ingester:

  1. converts scope pulse widths (seconds) to cycles via the run clock,
  2. subtracts the calibrated empty-bracket overhead from every sample,
  3. records p50/p99/p999 + sample_count for the scope-derived ``cycles`` metric
     (the decision-bearing timing number, with ``value`` = p50) and the
     corroborating ``cycles_dwt`` metric, and
  4. computes the scope-vs-DWT cross-check (relative error of the medians) and
     persists it as ``cycles_xcheck_rel_error`` for the audit trail.

The scope is the primary timing instrument; the DWT count is the cross-check.
Brontes remains the sole flash/probe/ITM/SWO authority -- this ingester only
consumes evidence it already produced.

Report shape (project-neutral)::

    {
      "run": "zydeco-9.4.9.2-cycles",
      "tool_version": "0.1.0",
      "clock_hz": 170000000,
      "xcheck_tolerance": 0.05,
      "bracket_overhead_cycles": 12.0,      # scope bracket; also accepted in provenance
      "dwt_bracket_overhead_cycles": 4.0,   # optional, default 0
      "provenance": {"board_id": "...", "probe_serial": "...",
                     "scope_device": "Analog Discovery 2 / SN...",
                     "bracket_overhead_cycles": 12.0, "toolchain_commit": "..."},
      "cells": [
        {"name": "cell1_c_hal", "language": "c11", "drivers": "hal",
         "is_baseline": true,
         "regions": [
           {"region": "uart_tx",
            "scope_pulse_widths_s": [1.21e-6, 1.20e-6, ...],   # OR scope_cycles
            "dwt_cycles": [205, 204, 206, ...]}                # optional
         ]}
      ]
    }

A region may instead supply pre-converted ``scope_cycles`` directly. Idempotent:
re-ingesting the same report converges to the same rows.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from zydeco_profiler_mcp.analytics.stats import percentiles
from zydeco_profiler_mcp.ingest.common import (
    get_or_create_cell,
    get_or_create_metric,
    get_or_create_region,
    get_or_create_run,
    set_provenance,
    upsert_measurement,
)

CYCLES = "cycles"
CYCLES_DWT = "cycles_dwt"
CYCLES_XCHECK = "cycles_xcheck_rel_error"


@dataclass(frozen=True)
class XCheck:
    """Scope-vs-DWT corroboration for one (cell, region)."""

    cell: str
    region: str
    scope_p50: float
    dwt_p50: float | None
    rel_error: float | None
    within_tolerance: bool | None


@dataclass(frozen=True)
class CycleIngestReport:
    rows: int
    xchecks: tuple[XCheck, ...]
    out_of_tolerance: tuple[XCheck, ...]


def _scope_cycles(region: dict, clock_hz: float, overhead: float) -> list[float]:
    if "scope_cycles" in region:
        raw = [float(v) for v in region["scope_cycles"]]
    elif "scope_pulse_widths_s" in region:
        if not clock_hz:
            raise ValueError("clock_hz required to convert scope_pulse_widths_s to cycles")
        raw = [float(w) * float(clock_hz) for w in region["scope_pulse_widths_s"]]
    else:
        raise ValueError(
            f"region {region.get('region')!r} has neither scope_cycles "
            "nor scope_pulse_widths_s"
        )
    return [max(0.0, v - overhead) for v in raw]


def _dwt_cycles(region: dict, overhead: float) -> list[float]:
    return [max(0.0, float(v) - overhead) for v in region.get("dwt_cycles", [])]


def ingest_cycle_report(conn: sqlite3.Connection, report: dict) -> CycleIngestReport:
    label = report["run"]
    created_at = report.get("created_at") or datetime.now(UTC).isoformat()
    run_id = get_or_create_run(
        conn, label, created_at=created_at, tool_version=report.get("tool_version")
    )

    provenance = dict(report.get("provenance", {}))
    clock_hz = float(report.get("clock_hz") or 0.0)
    scope_overhead = float(
        report.get("bracket_overhead_cycles")
        if report.get("bracket_overhead_cycles") is not None
        else provenance.get("bracket_overhead_cycles", 0.0)
    )
    dwt_overhead = float(report.get("dwt_bracket_overhead_cycles", 0.0))
    tolerance = float(report.get("xcheck_tolerance", 0.05))
    # The scope bracket overhead lives on the run row for provenance.
    provenance.setdefault("bracket_overhead_cycles", scope_overhead)
    set_provenance(conn, run_id, provenance)

    cycles_id = get_or_create_metric(conn, CYCLES, unit="cycles", lower_is_better=True)
    dwt_id = get_or_create_metric(conn, CYCLES_DWT, unit="cycles", lower_is_better=True)
    xcheck_id = get_or_create_metric(conn, CYCLES_XCHECK, unit="ratio", lower_is_better=True)

    rows = 0
    xchecks: list[XCheck] = []
    for cell in report["cells"]:
        cell_id = get_or_create_cell(
            conn,
            run_id,
            cell["name"],
            language=cell.get("language"),
            drivers=cell.get("drivers"),
            is_baseline=bool(cell.get("is_baseline", False)),
        )
        for region in cell.get("regions", []):
            region_id = get_or_create_region(conn, region["region"])

            scope = _scope_cycles(region, clock_hz, scope_overhead)
            scope_pct = percentiles(scope)
            if scope_pct is None:
                raise ValueError(
                    f"cell {cell['name']!r} region {region['region']!r} has no scope samples"
                )
            upsert_measurement(
                conn,
                run_id=run_id,
                cell_id=cell_id,
                region_id=region_id,
                metric_id=cycles_id,
                value=scope_pct["p50"],
                p50=scope_pct["p50"],
                p99=scope_pct["p99"],
                p999=scope_pct["p999"],
                sample_count=len(scope),
            )
            rows += 1

            dwt = _dwt_cycles(region, dwt_overhead)
            dwt_pct = percentiles(dwt)
            rel_error: float | None = None
            within: bool | None = None
            if dwt_pct is not None:
                upsert_measurement(
                    conn,
                    run_id=run_id,
                    cell_id=cell_id,
                    region_id=region_id,
                    metric_id=dwt_id,
                    value=dwt_pct["p50"],
                    p50=dwt_pct["p50"],
                    p99=dwt_pct["p99"],
                    p999=dwt_pct["p999"],
                    sample_count=len(dwt),
                )
                rows += 1
                if dwt_pct["p50"] != 0.0:
                    rel_error = abs(scope_pct["p50"] - dwt_pct["p50"]) / dwt_pct["p50"]
                    within = rel_error <= tolerance
                    upsert_measurement(
                        conn,
                        run_id=run_id,
                        cell_id=cell_id,
                        region_id=region_id,
                        metric_id=xcheck_id,
                        value=rel_error,
                        sample_count=1,
                    )
                    rows += 1

            xchecks.append(
                XCheck(
                    cell=cell["name"],
                    region=region["region"],
                    scope_p50=scope_pct["p50"],
                    dwt_p50=dwt_pct["p50"] if dwt_pct is not None else None,
                    rel_error=rel_error,
                    within_tolerance=within,
                )
            )

    conn.commit()
    out_of_tolerance = tuple(x for x in xchecks if x.within_tolerance is False)
    return CycleIngestReport(
        rows=rows, xchecks=tuple(xchecks), out_of_tolerance=out_of_tolerance
    )
