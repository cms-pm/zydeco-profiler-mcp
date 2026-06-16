# SPDX-License-Identifier: MIT
from __future__ import annotations

from zydeco_profiler_mcp.analytics.decision import apply_rule

LIB = {"flash_bytes": True, "sram_bytes": True, "cycles": True}
MARGINS = {"flash_bytes": 0.02, "sram_bytes": 0.02, "cycles": 0.05}


def test_go_when_non_inferior_and_strict_win():
    base = {"flash_bytes": 6000, "sram_bytes": 800, "cycles": 1000}
    cand = {"flash_bytes": 5200, "sram_bytes": 790, "cycles": 900}  # flash + cycles strict win
    decision = apply_rule(base, cand, margins=MARGINS, lower_is_better=LIB)
    assert decision.verdict == "go"


def test_no_go_on_regression_beyond_margin():
    base = {"flash_bytes": 6000, "sram_bytes": 800, "cycles": 1000}
    cand = {"flash_bytes": 5200, "sram_bytes": 900, "cycles": 900}  # sram +12.5% > 2% margin
    decision = apply_rule(base, cand, margins=MARGINS, lower_is_better=LIB)
    assert decision.verdict == "no_go"
    assert "sram_bytes" in decision.reason


def test_no_go_when_no_strict_win():
    base = {"flash_bytes": 6000, "sram_bytes": 800, "cycles": 1000}
    cand = {"flash_bytes": 6010, "sram_bytes": 805, "cycles": 1010}  # within margin, no win
    decision = apply_rule(base, cand, margins=MARGINS, lower_is_better=LIB)
    assert decision.verdict == "no_go"
    assert "no strict win" in decision.reason


def test_higher_is_better_metric():
    lib = {"throughput": False}
    margins = {"throughput": 0.05}
    base = {"throughput": 100.0}
    cand = {"throughput": 110.0}  # +10% > 5% margin -> strict win
    decision = apply_rule(base, cand, margins=margins, lower_is_better=lib)
    assert decision.verdict == "go"
