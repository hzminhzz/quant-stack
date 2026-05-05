# Migration Log

## Phase 0 - Safety and baseline

Status: complete.

- Captured repo baseline in `docs/refactor/BASELINE.md`.
- Removed hardcoded DeepSeek-style key values from source.
- Added `DEEPSEEK_API_KEY` environment loading and `.env.example`.
- Added root `.env` ignore rules.
- Documented the current pytest blocker: missing `antlr4` during Hydra/OmegaConf plugin loading.

## Phase 1 - Package skeleton and compatibility

Status: complete.

### Import compatibility findings

Current code imports these root-level modules directly:

```text
engine
strategy_families
pipeline_artifacts
discovery
research
live_swarm
```

These paths are used by tests, top-level scripts, and `MLEvolve/`. Moving files now would break imports and likely create a namespace collision with `MLEvolve/engine`, which also imports from an `engine` package internally.

### Compatibility decision

Phase 1 creates the destination package skeleton and legacy placeholders only. Existing root-level modules remain the active compatibility surface until each module has a tested shim or wrapper.

No production code was moved in this phase.

### Verification

```bash
uv run python -c "import quant_stack, quant_stack.data, quant_stack.indicators.polars, quant_stack.indicators.talib, quant_stack.indicators.live, quant_stack.strategies.rsi_sma, quant_stack.strategies.bb_breakout, quant_stack.strategies.grid, quant_stack.backtesting, quant_stack.live.broker_adapters, quant_stack.research, quant_stack.artifacts, quant_stack.cli, legacy, legacy.strategy_families, legacy.backtesters, legacy.scripts; print('phase1 skeleton imports ok')"
```

Result: passed.

```bash
uv run python -c "import engine, strategy_families, pipeline_artifacts, live_swarm; print('legacy root imports ok')"
```

Result: passed.

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed.

```bash
uv run pytest
```

Result: still fails before test collection with the pre-existing `ModuleNotFoundError: No module named 'antlr4'` pytest plugin/import issue documented in `BASELINE.md`.

### Skeleton created

```text
quant_stack/
  data/
  indicators/
    polars/
    talib/
    live/
  strategies/
    rsi_sma/
    bb_breakout/
    grid/
  backtesting/
  live/
    broker_adapters/
  research/
  artifacts/
  cli/
legacy/
  strategy_families/
  backtesters/
  scripts/
```

### Next Phase 1 step before any moves

Create explicit compatibility modules only when a real module is migrated. For example, after moving `pipeline_artifacts.py` to `quant_stack/artifacts/store.py`, keep the root `pipeline_artifacts.py` as a thin re-export until all call sites are updated.

## Phase 2 - Data layer

Status: complete.

### Implemented

- Added canonical OHLCV schema constants in `quant_stack/data/schemas.py`.
- Added Polars-only validation and normalization in `quant_stack/data/validation.py`.
- Added Parquet eager/lazy loaders in `quant_stack/data/loaders.py`.
- Added OHLCV resampling in `quant_stack/data/resample.py`.
- Exported the public data-layer API from `quant_stack/data/__init__.py`.
- Added focused tests in `test_quant_stack_data.py`.

### Data contract

Required columns:

```text
timestamp, open, high, low, close, volume
```

Normalization accepts datetime/date timestamps, epoch-millisecond integer timestamps, and parseable datetime strings. Output uses a datetime `timestamp` and Float64 OHLCV values.

Validation checks required columns, nulls, duplicate timestamp keys, negative volume, high/low OHLC bounds, and sorted output. Unsorted input is sorted by default.

Resampling uses first open, max high, min low, last close, and summed volume.

### Verification

```bash
uv run python -m unittest test_quant_stack_data.py
```

Result: passed, 9 tests.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest test_quant_stack_data.py
```

Result: passed, 9 tests.

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed.

Full `uv run pytest` remains blocked by the pre-existing `antlr4` plugin/import issue documented in `BASELINE.md`.

## Phase 11 - Typed research orchestration (PydanticAI boundary)
Status: complete.

Implemented typed research/orchestration modules under `quant_stack/research/`:

- `schemas.py`: `StrategyIdea`, `FeatureIdea`, `CandidateParams`, `ExperimentPlan`, `ResearchCritique`, `BacktestSummary`, `ValidationReport`, and queue types (`RejectionReason`, `ExperimentStatus`, `ExperimentRecord`).
- `guards.py`: hard rejections for future-data lookahead, broker/live execution mentions, and missing deterministic strategy logic.
- `experiment_queue.py`: deterministic queue with explicit status transition rules and JSON persistence snapshot; rejected transitions require `rejection_reason`.
- `tools.py`: safe boundary tools (`list_registered_strategies`, `submit_experiment`, `request_backtest_from_plan`) using strategy registry + `PolarsSignalBacktester` + validation + artifact store only.
- `prompts.py`, `agents.py`, `reports.py`: thin PydanticAI wrappers with typed outputs and deterministic report rendering.
- `__init__.py`: exports updated.

Added focused tests:

- `tests/research/test_schemas.py`
- `tests/research/test_guards.py`
- `tests/research/test_experiment_queue.py`
- `tests/research/test_ai_tool_boundaries.py`

Verification:

```bash
uv run python -m unittest tests.research.test_schemas tests.research.test_guards tests.research.test_experiment_queue tests.research.test_ai_tool_boundaries
```

Result: passed, 16 tests.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/research/test_schemas.py tests/research/test_guards.py tests/research/test_experiment_queue.py tests/research/test_ai_tool_boundaries.py
```

Result: passed, 16 tests.

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed.

Boundary guarantee: `quant_stack/research/tools.py` does not import broker adapters, live execution, `ccxt`, or `subprocess`.

## Phase 12 - Agentic strategy optimizer
Status: complete.

Implemented `quant_stack/research/optimization/` as a research-only replacement for the old `live_swarm.py` optimization concept.

Created modules:

- `schemas.py`
- `objective.py`
- `critic.py`
- `optimizer_agent.py`
- `loop.py`
- `memory.py`
- `guards.py`
- `__init__.py`

Created tests:

- `tests/research/optimization/test_schemas.py`
- `tests/research/optimization/test_objective.py`
- `tests/research/optimization/test_guards.py`
- `tests/research/optimization/test_loop.py`
- `tests/research/optimization/test_memory.py`

Concepts migrated from `live_swarm.py`:

- bounded actor/critic iteration loop
- typed agent outputs
- deterministic scoring/validation gate before approval
- fallback model wrapper pattern (in new typed agent wrappers)
- structured run/candidate memory and artifact persistence

Concepts deliberately not migrated:

- `strategy_families` dependency
- mandatory live orderbook/trade context
- direct `engine.evaluator` coupling
- hardcoded CRO thresholds in prompt policy
- broker/live execution paths and live entrypoint semantics

Verification:

```bash
uv run python -m unittest tests.research.optimization.test_schemas tests.research.optimization.test_objective tests.research.optimization.test_guards tests.research.optimization.test_loop tests.research.optimization.test_memory
```

Result: passed, 15 tests.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/research/optimization/test_schemas.py tests/research/optimization/test_objective.py tests/research/optimization/test_guards.py tests/research/optimization/test_loop.py tests/research/optimization/test_memory.py
```

Result: passed, 15 tests.

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed.

## Phase 5 - Polars signal backtester
Status: complete.

Implemented `quant_stack/backtesting/polars_engine.py` plus cost, fill, base, and result contracts. The Polars engine applies the anti-lookahead rule explicitly with `position = signal.shift(1)`, computes close-to-close asset returns, charges costs only on position changes, and emits equity/exposure columns plus metrics and trade returns.

## Phase 6 - Metrics and validation
Status: complete.

Implemented `quant_stack/backtesting/metrics.py`, `monte_carlo.py`, and `contracts.py`. Metrics preserve negative drawdown semantics. Validation returns pass/fail with reasons rather than raising as the default API. Monte Carlo is deterministic for a fixed seed.

## Phase 7 - vectorbt adapter
Status: complete.

Implemented `quant_stack/backtesting/vectorbt_engine.py` as an optional adapter. `vectorbt` is imported lazily inside `run()`, so core imports and strategy modules do not require vectorbt or pandas. Strategy modules remain engine-agnostic.

## Phase 8 - Live NumPy/Numba state
Status: complete.

Implemented live indicator state adapters:

- `EMAState`
- `RSIState`
- `RollingStdState`
- `BollingerBandState`

Also added minimal live contracts for environment checks, order intent, risk clamping, and live state vectors.

## Phase 9 - Research workflow decoupling
Status: complete.

Implemented decoupled schemas and storage in `quant_stack/artifacts/`, plus research helpers in `quant_stack/research/`. Generated code is explicitly marked as non-production research output and does not become execution authority.

## Phase 10 - CLI
Status: complete.

Implemented CLI modules:

- `quant_stack/cli/run_backtest.py`
- `quant_stack/cli/run_walk_forward.py`
- `quant_stack/cli/run_research.py`
- `quant_stack/cli/run_live_env.py`

The walk-forward command is scaffolded, while backtest/research/live-env commands are functional additive entrypoints.

## Phase 5-10 verification

```bash
uv run python -m unittest test_quant_stack_backtesting_live_research_cli.py
```

Result: passed, 14 tests.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest test_quant_stack_backtesting_live_research_cli.py test_quant_stack_indicators_strategies.py test_quant_stack_data.py
```

Result: passed, 35 tests.

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed.

Full `uv run pytest` remains blocked by the pre-existing `antlr4` plugin/import issue documented in `BASELINE.md`.

## Phase 3 - Polars indicators

Status: complete.

### Implemented

- Added `quant_stack/indicators/polars/trend.py` with SMA, EMA, rolling high, and rolling low expressions.
- Added `quant_stack/indicators/polars/momentum.py` with simple rolling RSI.
- Added `quant_stack/indicators/polars/volatility.py` with rolling volatility, rolling z-score, true range, and ATR.
- Added `quant_stack/indicators/polars/bands.py` with Bollinger Bands using population standard deviation.
- Added `quant_stack/indicators/polars/returns.py` with simple and log returns.
- Exported the public indicator API from `quant_stack/indicators/polars/__init__.py`.

### Semantics note

The batch RSI expression uses simple rolling average gains/losses. Legacy `engine/backtester.py` uses Wilder-smoothed RSI. Wilder/live parity is intentionally deferred to the live NumPy/Numba state phase rather than hidden inside the first Polars batch implementation.

### Verification

Indicator fixtures are covered by `test_quant_stack_indicators_strategies.py`:

- SMA
- EMA
- rolling high/low
- simple returns
- log returns
- Bollinger Bands
- simple rolling RSI
- rolling volatility
- rolling z-score
- ATR

## Phase 4 - Strategy registry
Status: complete.

### Implemented

- Added `quant_stack/strategies/specs.py` with `StrategySpec`, `SignalBuilder`, and `LiveStateAdapter` contracts.
- Added `quant_stack/strategies/registry.py` with `StrategyRegistry`, `StrategyModule`, `available_strategies()`, and `get_strategy()`.
- Added `quant_stack/strategies/rsi_sma/` with params, spec, signals, live-state placeholder, and module factory.
- Added `quant_stack/strategies/bb_breakout/` with params, spec, signals, live-state placeholder, and module factory.
- Added `quant_stack/strategies/grid/` with params, spec, path-dependent placeholder signals, live-state placeholder, and module factory.

### Strategy boundary

New strategy packages build deterministic features/signals only. They do not import backtesters, brokers, LLM orchestration, artifacts, or legacy `strategy_families` modules.

The grid strategy is registered as `path_dependent` with default engine `vectorbt`; it exposes parameter/order-intent columns rather than pretending to be a stateless signal strategy.

### Verification

```bash
uv run python -m unittest test_quant_stack_indicators_strategies.py
```

Result: passed, 12 tests.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest test_quant_stack_indicators_strategies.py test_quant_stack_data.py
```

Result: passed, 21 tests.

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed.

Full `uv run pytest` remains blocked by the pre-existing `antlr4` plugin/import issue documented in `BASELINE.md`.
