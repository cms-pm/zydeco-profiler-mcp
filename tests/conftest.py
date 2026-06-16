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
