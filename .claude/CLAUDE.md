# CLAUDE.md — Agent bootstrap for quant-stack

This file is a quick-start for AI coding agents. Full governance lives in `AGENTS.md`.

## Start sequence (strict)

1. Read `AGENTS.md`
2. Read `docs/REPO_MAP.md`
3. Work in `quant_stack/` (canonical path)
4. Use CLI entrypoint: `uv run python -m quant_stack.cli.main ...`

## Repository summary

`quant-stack` is a Polars-first algorithmic trading research/backtesting framework.

## High-value code surfaces

| Path | Why it matters |
|---|---|
| `quant_stack/cli/main.py` | Canonical command dispatcher |
| `quant_stack/strategies/registry.py` | Strategy registration + module surface |
| `quant_stack/backtesting/` | Generic engines + result normalization |
| `quant_stack/data/` | Canonical market data loaders |
| `quant_stack/features/` | Feature pipeline + validation |
| `quant_stack/workflows/` | Orchestration layer |

## Hard boundaries (do not violate)

- No pandas in deterministic core (`backtesting/`, `indicators/`, `live/`)
- No LLM imports in deterministic engines
- No strategy-specific backtesters inside generic engines
- Canonical source data is 1m candles; derive higher timeframes deterministically
- No lookahead in multi-timeframe visibility

## Large-data handling (important)

- Do not load full parquet/CSV into context
- Only inspect schema, row counts, min/max timestamps, and small head/tail slices
- Prefer reading summary artifacts (`summary.json`, `run_config.json`) after runs

## Low-priority paths (skip unless explicitly needed)

- `_archive/` (legacy)
- `_artifacts/` / `artifacts/` / `reports/` (generated outputs)
- `data/` large raw datasets (read minimally)

## Canonical verification

```bash
uv run pytest tests/architecture/test_architecture_boundaries.py -q
```
