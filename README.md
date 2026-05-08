# quant-stack

Algorithmic trading research + deterministic backtesting framework (Polars-first).

## If you are an AI agent (read this first)

1. Read `AGENTS.md` (architecture boundaries and hard constraints)
2. Read `docs/REPO_MAP.md` (canonical vs legacy paths)
3. Prefer `quant_stack/` for all new implementation work
4. Avoid `_archive/` and generated artifacts by default; inspect market data/parquet only when needed, and then minimally (schema/stats/small slices)

## Canonical CLI entrypoint

```bash
uv run python -m quant_stack.cli.main --help
```

Supported commands:
- `backtest`
- `experiment`
- `build-bybit-dataset`
- `research`
- `live-env`
- `walk-forward`
- `acceptance`
- `phase19`
- `inspect-data`
- `duckdb-query`
- `open-report`
- `api-tools`

## High-value code surfaces

```text
quant_stack/
├── cli/                     # Canonical workflows / command dispatch
├── strategies/              # Strategy modules and params/signals
├── backtesting/             # Generic engines + BacktestResult normalization
├── data/                    # Parquet scanning/loading utilities
├── features/                # Feature engineering + validation
├── workflows/               # Workflow orchestration
├── research/                # Research / acceptance / optimization orchestration
└── api/                     # Tool endpoints + MCP adapter
```

## Architecture rules (must keep)

- No pandas in deterministic core (`backtesting/`, `indicators/`, `live/`)
- No LLM imports in deterministic engines
- No strategy-specific backtesters in generic engines (keep strategy logic in `quant_stack/strategies/`)
- Canonical market source is 1m parquet; derive higher timeframes deterministically
- No-lookahead for multi-timeframe alignment (visibility only after candle close)

## Minimal developer commands

```bash
# Run fast architecture safety checks
uv run pytest tests/architecture/test_architecture_boundaries.py -q

# Run full test suite
uv run pytest tests/ -q
```

## DuckDB analytical-layer workflow

Use DuckDB for large parquet SQL filtering/joining, then hand off to Polars.

```bash
uv run python -m quant_stack.cli.main duckdb-query \
  --query "SELECT * FROM read_parquet('data/*/*.parquet') LIMIT 1000" \
  --memory-limit 4GB \
  --temp-directory /tmp/duckdb_spill \
  --output-path artifacts/duckdb/staged.parquet
```

## API tools docs

See `docs/api_tools_integration.md` for `api-tools` command usage and MCP-style calls.
