# Repo Map

This document is the **Phase 0 navigation map** for the repository.

Its purpose is simple:

- tell humans and agents which paths are canonical,
- identify legacy/reference paths that should not be copied by default,
- reduce accidental creation of parallel workflows.

## Canonical Rule

`quant_stack/` is the canonical reusable package root.

If you are adding new reusable code, start by checking:

- `quant_stack/strategies/`
- `quant_stack/backtesting/`
- `quant_stack/data/`
- `quant_stack/features/`
- `quant_stack/workflows/`
- `quant_stack/research/`
- `quant_stack/cli/`

---

## Top-Level Ownership Map

| Path | Status | Purpose | Default for new work? |
|---|---|---|---|
| `quant_stack/` | Canonical | Main reusable package | Yes |
| `tests/` | Canonical | Main test suite | Yes |
| `docs/` | Canonical | Architecture, workflows, migration docs | Yes |
| `examples/` | Canonical | Query/config examples | Yes |
| `scripts/` | Operational | CLI wrappers and operational entrypoints | Only if kept thin |
| `artifacts/` | Generated | Local generated outputs | No |
| `reports/` | Generated | Local reports | No |
| `data/` | Local data | Local working datasets | No |
| `legacy/` | Legacy | Deprecated systems | No |

---

## Canonical Workflow Surfaces

These are the main package-first surfaces agents should inspect before inventing anything custom.

### Strategies

- `quant_stack/strategies/registry.py`
- `quant_stack/strategies/*/params.py`
- `quant_stack/strategies/*/signals.py`
- `quant_stack/strategies/*/module.py`

### Backtesting

- `quant_stack/backtesting/results.py` → `BacktestResult`
- `quant_stack/backtesting/polars_engine.py` → `PolarsSignalBacktester`
- `quant_stack/backtesting/costs.py` → `CostModel`
- `quant_stack/backtesting/fills.py` → `FillPolicy`
- `quant_stack/backtesting/metrics.py` → `calculate_metrics`

### Data / Features

- `quant_stack/data/`
- `quant_stack/features/pipeline.py`
- `quant_stack/features/validation.py`

### Workflow / Experiment / Acceptance

- `quant_stack/workflows/engine.py`
- `quant_stack/research/experiments/runner.py`
- `quant_stack/research/acceptance_artifacts.py`
- `quant_stack/workflows/acceptance.py` (canonical wrapper)
- `scripts/run_pipeline_acceptance.py` (compatibility-backed harness surface)

### Optimization / Research Orchestration

- `quant_stack/research/optimization/`
- `quant_stack/research/phase_orchestration/`

---

## Root-Level Intent

The root directory should converge toward:

- project metadata,
- docs,
- tests,
- examples,
- thin scripts,
- local data,
- generated artifacts,
- explicit legacy folders.

The root should **not** continue to grow new business logic, new backtest engines, new strategy registries, or custom reporting systems.

---

## Practical Rule For Agents

When uncertain, inspect in this order:

1. `AGENTS.md`
2. `docs/REPO_MAP.md`
3. `quant_stack/strategies/registry.py`
4. `quant_stack/backtesting/`
5. `quant_stack/data/` and `quant_stack/features/`
6. `quant_stack/workflows/` and `quant_stack/research/`

Only inspect legacy paths after you know the canonical path does not already solve the task.