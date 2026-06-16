# SPDX-License-Identifier: MIT
"""zydeco-profiler-mcp command line.

    zydeco-profiler-mcp init <db>
    zydeco-profiler-mcp ingest-size <db> <report.json>
    zydeco-profiler-mcp ingest-cycles <db> <report.json>
    zydeco-profiler-mcp runs <db>
    zydeco-profiler-mcp pareto <db> --run <id> --metrics flash_bytes,sram_bytes
    zydeco-profiler-mcp decide <db> --run <id> --baseline <cell> --candidate <cell> \
        --margins flash_bytes=0.02,sram_bytes=0.02,cycles=0.05
    zydeco-profiler-mcp serve            # read-only MCP server over stdio
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from zydeco_profiler_mcp import __version__, api
from zydeco_profiler_mcp import db as _db


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def _parse_kv_floats(spec: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, _, value = pair.partition("=")
        out[key.strip()] = float(value)
    return out


def _cmd_init(args: argparse.Namespace) -> int:
    conn = _db.connect(args.db)
    try:
        _db.migrate(conn)
    finally:
        conn.close()
    _print({"db": str(args.db), "status": "migrated"})
    return 0


def _cmd_ingest_size(args: argparse.Namespace) -> int:
    from zydeco_profiler_mcp.ingest.size import ingest_size_report

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    conn = _db.connect(args.db)
    try:
        _db.migrate(conn)
        result = ingest_size_report(conn, report)
    finally:
        conn.close()
    _print({"db": str(args.db), "ingested_rows": result.rows})
    return 0


def _cmd_ingest_cycles(args: argparse.Namespace) -> int:
    from zydeco_profiler_mcp.ingest.cycles import ingest_cycle_report

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    conn = _db.connect(args.db)
    try:
        _db.migrate(conn)
        result = ingest_cycle_report(conn, report)
    finally:
        conn.close()
    _print(
        {
            "db": str(args.db),
            "ingested_rows": result.rows,
            "xchecks": len(result.xchecks),
            "out_of_tolerance": [
                {"cell": x.cell, "region": x.region, "rel_error": x.rel_error}
                for x in result.out_of_tolerance
            ],
        }
    )
    return 0 if not result.out_of_tolerance else 1


def _cmd_runs(args: argparse.Namespace) -> int:
    _print(api.list_runs(args.db))
    return 0


def _cmd_pareto(args: argparse.Namespace) -> int:
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
    _print(api.pareto(args.db, args.run, metrics))
    return 0


def _cmd_decide(args: argparse.Namespace) -> int:
    margins = _parse_kv_floats(args.margins)
    _print(api.decide(args.db, args.run, args.baseline, args.candidate, margins))
    return 0


def _cmd_serve(_args: argparse.Namespace) -> int:
    from zydeco_profiler_mcp.mcp_server import run_stdio

    run_stdio()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zydeco-profiler-mcp")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create/migrate the store")
    p_init.add_argument("db")
    p_init.set_defaults(func=_cmd_init)

    p_ing = sub.add_parser("ingest-size", help="ingest a code-size report")
    p_ing.add_argument("db")
    p_ing.add_argument("report")
    p_ing.set_defaults(func=_cmd_ingest_size)

    p_ingc = sub.add_parser("ingest-cycles", help="ingest an on-target cycle report")
    p_ingc.add_argument("db")
    p_ingc.add_argument("report")
    p_ingc.set_defaults(func=_cmd_ingest_cycles)

    p_runs = sub.add_parser("runs", help="list runs")
    p_runs.add_argument("db")
    p_runs.set_defaults(func=_cmd_runs)

    p_par = sub.add_parser("pareto", help="Pareto frontier for a run")
    p_par.add_argument("db")
    p_par.add_argument("--run", type=int, required=True)
    p_par.add_argument("--metrics", required=True, help="comma-separated metric names")
    p_par.set_defaults(func=_cmd_pareto)

    p_dec = sub.add_parser("decide", help="apply the pre-registered decision rule")
    p_dec.add_argument("db")
    p_dec.add_argument("--run", type=int, required=True)
    p_dec.add_argument("--baseline", required=True)
    p_dec.add_argument("--candidate", required=True)
    p_dec.add_argument("--margins", required=True, help="metric=frac,... e.g. flash_bytes=0.02")
    p_dec.set_defaults(func=_cmd_decide)

    p_serve = sub.add_parser("serve", help="run the read-only MCP server (stdio)")
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
