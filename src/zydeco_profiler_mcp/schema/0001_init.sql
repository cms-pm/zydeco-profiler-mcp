-- zydeco-profiler-mcp core schema.
--
-- A generic, project-neutral benchmark matrix: measurements live on the
-- (run x cell x region x metric) grid, with provenance bound to the run row
-- (not reconstructed by archaeology). Migrations are idempotent: db.migrate()
-- re-runs every script, so every statement is CREATE ... IF NOT EXISTS and
-- ingest uses natural-key upserts.

-- A measurement campaign. One run = one coherent volley (e.g. the Zydeco
-- 3-cell size matrix, or a later cycle volley).
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY,
  label TEXT NOT NULL,
  tool_version TEXT,
  created_at TEXT NOT NULL,        -- ISO-8601 UTC
  UNIQUE(label)
);

-- Per-run software/hardware provenance, 1:1 with runs (run_id PK), so every
-- column depends on the key directly. Bound to the run, never reconstructed.
CREATE TABLE IF NOT EXISTS run_provenance (
  run_id INTEGER PRIMARY KEY REFERENCES runs(id),
  compiler_version TEXT,
  target_flags TEXT,
  toolchain_commit TEXT,
  elf_sha256 TEXT,
  map_sha256 TEXT,
  size_sha256 TEXT,
  board_id TEXT,                   -- HIL only
  probe_serial TEXT,               -- HIL only
  scope_device TEXT,               -- HIL only (WaveForms / Analog Discovery)
  bracket_overhead_cycles REAL     -- HIL only (calibrated empty-bracket subtract)
);

-- The regime under test within a run. For Zydeco: the 3-cell ladder
-- (C+HAL, C++17+HAL, C++17+custom-zero-cost-drivers).
CREATE TABLE IF NOT EXISTS cells (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  name TEXT NOT NULL,              -- e.g. 'cell1_c_hal'
  language TEXT,                   -- e.g. 'c11' | 'cpp17'
  drivers TEXT,                    -- e.g. 'hal' | 'custom_zero_cost'
  is_baseline INTEGER NOT NULL DEFAULT 0,
  UNIQUE(run_id, name)
);

-- Measured code regions (deduplicated by name across runs).
CREATE TABLE IF NOT EXISTS regions (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,              -- e.g. 'uart_tx', 'fsm_step', 'whole_image'
  UNIQUE(name)
);

-- Metric dimension (deduplicated by name). lower_is_better drives Pareto.
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,              -- 'flash_bytes' | 'sram_bytes' | 'cycles' | ...
  unit TEXT,                       -- 'bytes' | 'cycles'
  lower_is_better INTEGER NOT NULL DEFAULT 1,
  UNIQUE(name)
);

-- Fact table: one row per (run, cell, region, metric) observation. Percentile
-- columns carry cycle distributions; size metrics use value only.
CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  cell_id INTEGER NOT NULL REFERENCES cells(id),
  region_id INTEGER NOT NULL REFERENCES regions(id),
  metric_id INTEGER NOT NULL REFERENCES metrics(id),
  value REAL NOT NULL,             -- representative value (mean or single)
  p50 REAL,
  p99 REAL,
  p999 REAL,
  sample_count INTEGER NOT NULL DEFAULT 1,
  UNIQUE(run_id, cell_id, region_id, metric_id)
);

CREATE INDEX IF NOT EXISTS idx_measurements_run ON measurements(run_id);
CREATE INDEX IF NOT EXISTS idx_cells_run ON cells(run_id);
