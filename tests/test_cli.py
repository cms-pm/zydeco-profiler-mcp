# SPDX-License-Identifier: MIT
"""CLI exit-code contracts for the cycle/xcheck subcommands."""
from __future__ import annotations

import json

from zydeco_profiler_mcp.cli import main

_HZ = 170_000_000


def _widths(cycles_incl_overhead):
    return [c / _HZ for c in cycles_incl_overhead]


def _report(dwt_cell1):
    return {
        "run": "cli-cycles",
        "clock_hz": _HZ,
        "xcheck_tolerance": 0.05,
        "bracket_overhead_cycles": 12.0,
        "cells": [
            {
                "name": "cell1_c_hal",
                "is_baseline": True,
                "regions": [
                    {
                        "region": "uart_tx",
                        "scope_pulse_widths_s": _widths([212, 213, 211, 212, 214]),
                        "dwt_cycles": dwt_cell1,
                    }
                ],
            }
        ],
    }


def _write(tmp_path, report):
    db = tmp_path / "bench.db"
    rp = tmp_path / "cyc.json"
    rp.write_text(json.dumps(report), encoding="utf-8")
    return str(db), str(rp)


def test_ingest_cycles_exit0_then_xchecks(tmp_path, capsys):
    db, rp = _write(tmp_path, _report([201, 200, 202, 199, 201]))  # agrees with scope
    assert main(["init", db]) == 0
    assert main(["ingest-cycles", db, rp]) == 0
    capsys.readouterr()
    assert main(["xchecks", db, "--run", "1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["out_of_tolerance"] == []


def test_xchecks_tightened_tolerance_exits_1(tmp_path, capsys):
    db, rp = _write(tmp_path, _report([201, 200, 202, 199, 201]))
    main(["init", db])
    main(["ingest-cycles", db, rp])
    capsys.readouterr()
    assert main(["xchecks", db, "--run", "1", "--tolerance", "0.001"]) == 1


def test_ingest_cycles_exit1_when_scope_dwt_disagree(tmp_path, capsys):
    db, rp = _write(tmp_path, _report([100, 100, 100, 100, 100]))  # far from scope
    main(["init", db])
    capsys.readouterr()
    assert main(["ingest-cycles", db, rp]) == 1
    out = json.loads(capsys.readouterr().out)
    assert len(out["out_of_tolerance"]) == 1
