# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from zydeco_profiler_mcp import db as _db


SIZE_REPORT = {
    "run": "zydeco-9.4.9.1-size",
    "tool_version": "0.1.0.dev0",
    "provenance": {
        "compiler_version": "arm-none-eabi-gcc 13.2",
        "target_flags": "-mcpu=cortex-m4 -Os -fno-exceptions -fno-rtti",
        "elf_sha256": "deadbeef",
    },
    "metrics": [
        {"name": "flash_bytes", "unit": "bytes", "lower_is_better": True},
        {"name": "sram_bytes", "unit": "bytes", "lower_is_better": True},
    ],
    "cells": [
        {
            "name": "cell1_c_hal",
            "language": "c11",
            "drivers": "hal",
            "is_baseline": True,
            "measurements": [
                {"region": "whole_image", "metric": "flash_bytes", "value": 6000},
                {"region": "whole_image", "metric": "sram_bytes", "value": 800},
            ],
        },
        {
            "name": "cell2_cpp_hal",
            "language": "cpp17",
            "drivers": "hal",
            "measurements": [
                {"region": "whole_image", "metric": "flash_bytes", "value": 6050},
                {"region": "whole_image", "metric": "sram_bytes", "value": 800},
            ],
        },
        {
            "name": "cell3_cpp_custom",
            "language": "cpp17",
            "drivers": "custom_zero_cost",
            "measurements": [
                {"region": "whole_image", "metric": "flash_bytes", "value": 5200},
                {"region": "whole_image", "metric": "sram_bytes", "value": 760},
            ],
        },
    ],
}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "bench.db"


@pytest.fixture
def conn(db_path):
    c = _db.connect(db_path)
    _db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def size_report():
    return SIZE_REPORT


# Cycle volley: scope pulse widths (seconds) + corroborating DWT counts.
# clock = 170 MHz -> 1 cycle = 1/170e6 s. A 12-cycle bracket overhead is
# subtracted from every scope sample. cell3 is ~10% faster on uart_tx.
_HZ = 170_000_000
def _widths(cycles_incl_overhead):
    return [c / _HZ for c in cycles_incl_overhead]


CYCLE_REPORT = {
    "run": "zydeco-9.4.9.2-cycles",
    "tool_version": "0.1.0.dev0",
    "clock_hz": _HZ,
    "xcheck_tolerance": 0.05,
    "bracket_overhead_cycles": 12.0,
    "provenance": {
        "board_id": "stm32g474-nucleo",
        "probe_serial": "BRONTES-0001",
        "scope_device": "Analog Discovery 2 / SN210xxx",
    },
    "cells": [
        {
            "name": "cell1_c_hal",
            "language": "c11",
            "drivers": "hal",
            "is_baseline": True,
            "regions": [
                {
                    "region": "uart_tx",
                    # 200 cycles of work + 12 bracket overhead -> ~200 after subtract
                    "scope_pulse_widths_s": _widths([212, 213, 211, 212, 214]),
                    "dwt_cycles": [201, 200, 202, 199, 201],
                }
            ],
        },
        {
            "name": "cell3_cpp_custom",
            "language": "cpp17",
            "drivers": "custom_zero_cost",
            "is_baseline": False,
            "regions": [
                {
                    "region": "uart_tx",
                    "scope_pulse_widths_s": _widths([192, 193, 191, 192, 194]),
                    "dwt_cycles": [181, 180, 182, 179, 181],
                }
            ],
        },
    ],
}


@pytest.fixture
def cycle_report():
    return CYCLE_REPORT
