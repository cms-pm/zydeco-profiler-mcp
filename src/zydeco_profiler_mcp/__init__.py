# SPDX-License-Identifier: MIT
"""zydeco-profiler-mcp — a standalone, project-neutral benchmark-store MCP.

Ingests code-size and on-target cycle measurements into a provenance-bound
SQLite store and exposes Pareto/CI analytics plus a pre-registered
multi-objective decision rule over a read-only MCP surface.
"""
from __future__ import annotations

__version__ = "0.1.0.dev0"
