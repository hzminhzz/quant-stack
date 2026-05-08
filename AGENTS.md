# quant-stack Agent Governance

**CRITICAL: Only touch `quant_stack/` for new code and substantive logic. All other root directories are archived or for artifacts only.**

## Core Philosophy
- **Deterministic first**: Core engines (backtesting, indicators, live tick processing) must be pure, deterministic, and testable without external dependencies.
- **LLMs for planning, not execution**: Use LLMs for research planning, idea generation, and critique—but never inside deterministic trading engines.
- **Strategy-agnostic core**: The `quant_stack/backtesting` module provides generic backtest infrastructure. Strategy-specific logic lives in `quant_stack/strategies/`.
- **No pandas in core**: Core paths (`quant_stack/backtesting`, `quant_stack/indicators`, `quant_stack/live` tick loops) must use Polars or native Python. Pandas is allowed only in research/optimization exploration scripts.
- **No Polars in live tick step**: Live tick processing must use native Python or Polars without complex transformations. Keep it simple and fast.

## Architecture Boundaries

### Allowed
- `quant_stack/research/` - LLM-powered research, optimization, experiment orchestration
- `quant_stack/strategies/` - Strategy implementations (rsi_sma, bb_breakout, grid, etc.)
- `quant_stack/intelligence/` - Market intelligence gathering (OKX sources, scoring, normalization)
- `quant_stack/workflows/` - Workflow orchestration (actions, triggers, cooldown)

## Canonical Path Rules

- **`quant_stack/` is the canonical package root.** New reusable code should go there unless the task is explicitly about legacy compatibility.
- **Root-level scripts are thin entrypoints only.** Do not place new substantive backtesting, reporting, optimization, or orchestration logic in root scripts.
- **Do not create custom strategy-specific backtesters or custom report systems** when a canonical `quant_stack` workflow already exists.
- **Every public strategy backtest path should normalize to `BacktestResult`.**
- **When uncertain, inspect canonical workflow files first**: `quant_stack/strategies/registry.py`, `quant_stack/backtesting/`, `quant_stack/data/`, `quant_stack/features/`, `quant_stack/workflows/`, and `quant_stack/research/`.

### Forbidden in Core
- `quant_stack/backtesting/` - No strategy-specific backtesters, no LLM imports, no pandas
- `quant_stack/indicators/` - No LLM imports, no external API calls
- `quant_stack/live/tick_loop` - No LLM calls, no blocking I/O, no complex transformations

## Market Data Timeframe Policy

- **Canonical OHLCV source is 1-minute parquet**
  - Store and load raw market candles from the canonical 1m parquet dataset.
  - Higher timeframes must be synthesized from 1m data unless explicitly justified.
  - Do not require separate raw parquet files for 2m, 3m, 4m, 5m, 15m, 30m, 1h, 4h, or 1d if they can be derived from 1m.

- **Deterministic resampling only**
  - Open = first open in the window
  - High = max high in the window
  - Low = min low in the window
  - Close = last close in the window
  - Volume = sum volume in the window
  - Any quote volume, trade count, taker buy volume, or other exchange fields must use explicit deterministic aggregation rules.

- **No lookahead in multi-timeframe strategies**
  - Higher-timeframe candles are only available after the higher-timeframe candle closes.
  - A strategy running on 1m/5m must not use an unfinished 1h/4h candle as if it were final.
  - Forward-filled higher-timeframe indicators must be shifted so they only become visible after the source candle close.
  - Add tests when changing multi-timeframe alignment logic.

- **Do not ask user for derived timeframe files**
  - If a strategy needs 5m, 15m, 1h, or 4h candles, synthesize them from canonical 1m parquet.
  - Only ask for additional data if the requested logic cannot be represented from 1m OHLCV.

- **Exceptions requiring richer data**
  - Tick-level execution
  - Sub-minute scalping logic
  - L2/L3 orderbook modeling
  - Intrabar stop-loss/take-profit sequencing where both levels can be hit inside the same 1m candle
  - Exchange-native candle validation or reconciliation

- **Cache policy**
  - Derived higher-timeframe candles may be cached under _artifacts/cache or a dedicated derived-data cache.
  - Cached derived candles must be reproducible from canonical 1m parquet.
  - Cache keys should include symbol, source dataset id/path, timeframe, session/calendar rule, and resampling version.
  - Do not treat derived caches as source-of-truth raw data.

## Forbidden Patterns
1. **No pandas in core paths**
   - `quant_stack/backtesting/*.py`, `quant_stack/indicators/*.py`, `quant_stack/live/*.py`
2. **No LLM in deterministic engines**
   - Don't import pydantic_ai, openai, anthropic in backtesting/indicators/live
3. **No strategy-specific backtesters**
   - Don't add `run_rsi_backtest()`, `run_bb_backtest()` to `polars_engine.py`
4. **No live trading by default**
   - Research tasks must work without credentials or live broker connections
5. **No order-placement in research**
   - Don't import execution/broker modules in research/intelligence paths
6. **No private-key terms in research**
   - Don't have `api_secret`, `private_key`, `password` in research code
7. **No requesting derived timeframe datasets by default**
   - Do not ask for separate 5m/15m/1h/4h parquet files when canonical 1m parquet exists.
   - Build derived candles from 1m using deterministic resampling.

## Strategy Experiment Workflow
1. Define hypothesis in YAML (see `_archive/examples/pipeline_queries/`)
2. Generate deterministic fixtures (see `quant_stack/research/fixtures.py`)
3. Run baseline vs candidate with context gating
4. Validate no-lookahead, no-future-leakage
5. Artifact output includes proposed-only optimization record (never auto-executed)

## Legacy Code Policy
- `_archive/legacy/` - Deprecated code, do not extend
- `_archive/strategy_families/` - Deprecated code
- Do not move legacy modules to core paths
- Do not import legacy modules in new core code

## Artifact Policy
- Research artifacts go to `_artifacts/{experiment_name}/`
- Manifest always includes `timestamp: null` and `output_dir: "."` for determinism
- Optimization requests are always `status: "proposed"` - never auto-execute

## Testing Expectations
- All new code requires tests in `tests/`
- Architecture boundary tests in `tests/architecture/test_architecture_boundaries.py`
- Run: `uv run pytest tests/architecture/test_architecture_boundaries.py -q`
- Multi-timeframe data code requires tests for:
  - OHLCV aggregation correctness
  - missing 1m candle behavior
  - candle boundary alignment
  - no-lookahead / higher-timeframe close visibility
  - deterministic output from same input

## Engine Selection Is Mandatory
Before implementing or testing any strategy, classify it using its `StrategyCapabilities`.

### Engine decision tree
- **vectorbt** (vectorized): Only for simple signal strategies where entries/exits are independent, position is long/short/flat, no DCA, no pyramiding, no path-dependent state
- **polars signal**: For strategies producing clean entry/exit/position arrays needing repo-standard metrics
- **stateful**: For strategies with internal state, cooldowns, trailing stops, partial exits, re-entry gates, position sizing changes
- **grid_dca**: For strategies accumulating multiple entries, average price matters, DCA levels, multiple engines, basket exits
- **event_driven**: For strategies needing order type handling (limit/market), margin/funding/liquidation, bid/ask fill simulation

### Forbidden: vectorbt for complex strategies
Vectorbt/vectorized engines are **FORBIDDEN** for strategies with:
- DCA or grid logic
- Pyramiding or multi-leg baskets
- Average-price-dependent exits
- Partial exits
- Order-level state machines
- Margin/funding/liquidation behavior
- Bid/ask-sensitive fill logic

### Required: Every strategy must declare capabilities
Add `StrategyCapabilities` to every strategy spec:
```python
from quant_stack.strategies.specs import StrategySpec, StrategyCapabilities

SPEC = StrategySpec(
    name="my_strategy",
    default_engine="polars",
    capabilities=StrategyCapabilities(
        path_dependent=False,
        multi_leg=False,
        average_price_dependent=False,
        supports_vectorized=True,
    ),
)
```

Use `select_engine(spec)` to get the correct engine for any strategy.

## Data and Backtest Cost Control

**Critical: Agents must not read large market data files into context.**

### Forbidden Actions (Token Burn)
- Opening full CSV/parquet files into LLM context
- Printing full DataFrames
- Inspecting more than schema, row count, and first/last 5 rows
- Using LLM to reason over raw market data row-by-row
- Creating ad-hoc data inspection scripts for every backtest
- Reading full artifact parquet files into chat context

### Correct Workflow
```
LLM → chooses command → Python executes → artifacts saved → LLM reads summary.json
```

### For Large CSV/Parquet Files
- Do NOT open the full file
- Do NOT print full DataFrames
- Use `scan_ohlcv_parquet()` for lazy loading when possible
- Inspect only: schema, row count, null count, min/max timestamp, first/last 5 rows

### After a Run, Read Only
- `summary.json` - metrics summary
- `run_config.json` - configuration used
- First/last 20 trades if debugging
- Small logs only

### Canonical CLI Commands

All tasks must use the unified CLI entrypoint:

```bash
uv run python -m quant_stack.cli.main <command> [options]
```

Available commands:

| Command | Purpose | Example |
|---------|---------|---------|
| `backtest` | Single-strategy backtest | `--data-path <parquet> --strategy rsi_sma --start 2024-01-01 --end 2024-12-31` |
| `experiment` | Strategy comparison | `--config <yaml> --output-dir artifacts/` |
| `walk-forward` | Walk-forward optimization | `--config <yaml> --output-dir artifacts/` |
| `phase19` | Autonomous research pipeline | `--config <yaml>` |
| `build-bybit-dataset` | Market/feature dataset build | `--symbol BTCUSDT --timeframe 1m --output-dir artifacts/` |
| `research` | Research with paper context | `--paper-sources crossref,openalex` |
| `acceptance` | Phase 17 acceptance query | `--query <yaml> --output-dir artifacts/` |
| `inspect-data` | Inspect parquet schema/stats | `--path <parquet>` |
| `duckdb-query` | Out-of-core DuckDB SQL staging to parquet | `--query "SELECT ..." --output-path artifacts/staged.parquet` |

Do NOT use old script paths. Always use the CLI.

### Inspect Data Cheaply
For data inspection, use minimal output:
```bash
uv run python -c "import polars as pl; df = pl.scan_parquet('data.parquet'); print(df.schema)"
```

---

## Trade Idea Automation

When user submits a trade idea (new strategy concept or modifications):
1. **Automatically run Phase 17 acceptance** before proposing any optimization:
   ```bash
   uv run python -m quant_stack.cli.main acceptance --query <yaml> --output-dir _artifacts/<idea_name>/
   ```
2. Use `quant-stack-acceptance-runner` skill
3. Report validation results (pass/fail, metric deltas) before proceeding
4. Output artifacts to `_artifacts/{experiment_name}/`

---

## Agent Execution Protocol
1. Read `AGENTS.md` before any work
2. Prefer canonical paths under `quant_stack/` before inspecting legacy or root compatibility paths
3. Check architecture boundaries before adding imports
4. Run architecture tests after any import changes
5. Never modify trading logic without explicit user request
6. Never add live execution without explicit user request
7. Before requesting market data from the user, check whether the requested timeframe can be synthesized from canonical 1m parquet.
8. Prefer implementing or reusing deterministic resampling utilities over adding new timeframe-specific data files.

## Repo Skills

This repo provides specialized skills for quant-stack workflows. Use them via `load_skills` parameter:

| Skill | Use For |
|-------|---------|
| `quant-stack-executor` | Backtesting, dataset builds, strategy experiments |
| `quant-stack-boundary-guardian` | Checking architecture boundaries (no pandas in core, no LLM in engines) |
| `quant-stack-data-timeframe-guardian` | Multi-timeframe alignment, no-lookahead validation |
| `quant-stack-acceptance-runner` | Acceptance query workflows, context gating |
| `quant-stack-skill-creator` | Creating/ updating repo skills |

Example usage in task():
```python
task(category="deep", load_skills=["quant-stack-executor"], prompt="Run backtest...")
```

Skills are also available globally in ~/.config/opencode/skills/.
