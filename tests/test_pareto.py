# SPDX-License-Identifier: MIT
from __future__ import annotations

from zydeco_profiler_mcp.analytics.pareto import CellPoint, pareto_frontier


def test_frontier_drops_dominated_cell():
    lib = {"flash_bytes": True, "sram_bytes": True}
    points = [
        CellPoint("cell1_c_hal", True, {"flash_bytes": 6000, "sram_bytes": 800}),
        CellPoint("cell2_cpp_hal", False, {"flash_bytes": 6050, "sram_bytes": 800}),
        CellPoint("cell3_cpp_custom", False, {"flash_bytes": 5200, "sram_bytes": 760}),
    ]
    frontier = {p.cell for p in pareto_frontier(points, lib)}
    # cell3 dominates both others (smaller flash, <= sram); cell2 is dominated by cell1.
    assert frontier == {"cell3_cpp_custom"}


def test_frontier_keeps_tradeoffs():
    lib = {"flash_bytes": True, "cycles": True}
    points = [
        CellPoint("small_slow", False, {"flash_bytes": 5000, "cycles": 900}),
        CellPoint("big_fast", False, {"flash_bytes": 6000, "cycles": 700}),
    ]
    frontier = {p.cell for p in pareto_frontier(points, lib)}
    assert frontier == {"small_slow", "big_fast"}  # genuine trade-off, neither dominates
