# zydeco-profiler-mcp

A standalone, **project-neutral** benchmark-store MCP. It ingests code-size and
on-target cycle measurements into a provenance-bound SQLite store and exposes
**Pareto / CI analytics** plus a **pre-registered multi-objective decision rule**
over a read-only MCP surface.

It is the measurement backbone behind a *zero-cost-abstraction* decision — "does
the C++/custom-driver regime actually beat C + vendor HAL on **both** code size
**and** cycles?" — but the schema is generic (`runs × cells × regions × metrics`),
so any A/B/N embedded benchmark fits. It records and analyzes; it does **not**
drive hardware. Pair it with a probe/flash tool (e.g. `brontes-probe-mcp`) and a
bench instrument for the raw numbers.

> Origin: transformed from the author's `eval-grading` evidence-store tooling —
> the idempotent migration runner, read-only DuckDB SQL surface, Pareto/CI
> analytics, and determinism/idempotency discipline — retargeted from LLM eval to
> a generic embedded benchmark matrix.

## Install

```bash
pip install -e ".[dev]"
```

## CLI

```bash
zydeco-profiler-mcp init bench.db
zydeco-profiler-mcp ingest-size bench.db size_report.json
zydeco-profiler-mcp ingest-cycles bench.db cycle_report.json  # exit 1 if scope/DWT disagree
zydeco-profiler-mcp runs bench.db
zydeco-profiler-mcp pareto bench.db --run 1 --metrics flash_bytes,sram_bytes
zydeco-profiler-mcp decide bench.db --run 1 \
    --baseline cell1_c_hal --candidate cell3_cpp_custom \
    --margins flash_bytes=0.02,sram_bytes=0.02,cycles=0.05
zydeco-profiler-mcp xchecks bench.db --run 1 --tolerance 0.05  # exit 1 if any region disagrees
zydeco-profiler-mcp serve     # read-only MCP server over stdio
```

## MCP

Consume it like any MCP server (e.g. in `.mcp.json`):

```json
{
  "mcpServers": {
    "zydeco-profiler-mcp": {
      "command": "zydeco-profiler-mcp",
      "args": ["serve"],
      "env": { "ZYDECO_PROFILER_DB": "${PWD}/bench.db" }
    }
  }
}
```

Read-only tools: `list_runs`, `cells_summary`, `pareto`, `decide`, `query` (a
write-guarded SQL surface).

## The decision rule

A candidate regime beats the baseline only if it is **non-inferior** on every
gated metric (within a per-metric fractional margin) **and** achieves at least one
**strict win** beyond that margin. The rule is a pure function (`analytics.decision`)
so it can be frozen/pre-registered and replayed deterministically against recorded
evidence — no post-hoc tuning.

## License

MIT.
