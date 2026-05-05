# Refactor Blueprint

## Principle

Execute this refactor in staged, reversible phases. Phase 0 is safety and documentation only. Do not move architecture or rewrite production logic before the baseline is captured and secrets are cleaned up.

## Current diagnosis

The repo currently mixes research, validation, backtesting, live orchestration, and execution-generation concerns across top-level scripts and small packages.

Key issues:

- `strategy_families/StrategyFamily` combines prompts, paper queries, parameter validation, data preparation, simulation, and execution prompt generation.
- `engine/backtester.py`, `engine/backtester_bb.py`, and `engine/grid_backtester.py` are strategy-specific engines rather than a unified backtesting layer.
- `live_swarm.py` is both LLM orchestrator, live market context reader, deterministic validator, artifact handler, and fallback model wrapper.
- The project currently has no `quant_stack/` package root.
- Root `.gitignore` previously did not protect `.env` files.

## Target layering

```text
Research / LLM layer
    -> proposes ideas, hypotheses, and candidate params
Strategy layer
    -> deterministic feature and signal construction
Backtesting layer
    -> Polars signal engine or vectorbt adapter
Validation layer
    -> metrics, Monte Carlo, OOS, walk-forward
Live layer
    -> NumPy/Numba O(1) state update
Execution layer
    -> broker adapter, risk engine, paper/live trading
```

Strategy modules must not depend on the selected backtester, broker, LLM, or artifact store.

## Target package skeleton

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
  research/
  artifacts/
  cli/
legacy/
  strategy_families/
  backtesters/
  scripts/
docs/refactor/
```

## Phase 0 - Safety and baseline

Status: complete.

Tasks:

1. Run current tests and document results.
2. Run compile/import check and document failures.
3. Scan for hardcoded secrets.
4. Remove hardcoded DeepSeek key values from source.
5. Replace DeepSeek usage with `DEEPSEEK_API_KEY` env loading.
6. Add `.env.example`.
7. Ensure root `.env` files are ignored.
8. Create this blueprint and `BASELINE.md`.
9. Stop.

Acceptance criteria:

- Baseline document exists.
- Blueprint document exists.
- Test status is documented.
- Secret scan status is documented.
- Hardcoded DeepSeek-style key values are removed from source.
- No strategy/backtester architecture refactor is performed.

## Phase 1 - Package skeleton and compatibility

Status: complete.

Tasks:

1. Create the `quant_stack/` package skeleton.
2. Create `legacy/` directories.
3. Add compatibility shims before moving existing packages.
4. Move `strategy_families/` only after import compatibility is proven.
5. Move custom backtesters into `legacy/backtesters/` only after references are mapped.

Acceptance criteria:

- Existing tests import successfully or failures are explicitly documented.
- Old module paths remain available during migration.
- No legacy files are deleted.

## Phase 2 - Data layer

Status: complete.

Implement canonical OHLCV schema, validation, loaders, and resampling under `quant_stack/data/`.

Required OHLCV columns:

```text
timestamp, open, high, low, close, volume
```

Validation must check timestamp existence/casting, sorted rows, duplicate timestamps per symbol/timeframe, numeric OHLCV fields, non-null close, non-negative volume, and high/low consistency.

## Phase 3 - Polars indicators

Status: complete.

Implement historical indicators as Polars expressions under `quant_stack/indicators/polars/`:

```text
SMA, EMA, returns, log returns, rolling volatility, rolling z-score,
Bollinger Bands, RSI, ATR, rolling high/low
```

TA-Lib remains optional and isolated behind `quant_stack/indicators/talib/wrappers.py`.

## Phase 4 - Strategy registry

Status: complete.

Replace the overloaded family interface with:

```text
StrategySpec
StrategyRegistry
SignalBuilder
LiveStateAdapter
```

Strategy packages expose params, spec, signals, and optional live state only. They must not contain backtest, LLM prompt, artifact, or broker logic.

## Phase 5 - Polars signal backtester

Status: complete.

Implement a simple signal-based market-order engine under `quant_stack/backtesting/polars_engine.py`.

Required no-lookahead semantic:

```text
position = signal.shift(1)
```

Required tests:

- flat signal gives flat equity
- always-long matches buy-and-hold minus costs
- entry signal at bar `t` does not profit from the same bar
- fees apply only when position changes

## Phase 6 - Metrics and validation

Status: complete.

Move reusable analytics and Monte Carlo logic into `quant_stack/backtesting/` with explicit result contracts and pass/fail reasons.

## Phase 7 - vectorbt adapter

Status: complete.

Use vectorbt only behind `quant_stack/backtesting/vectorbt_engine.py` for path-dependent cases such as stops, limits, grid logic, partial exits, margin, and multi-asset portfolios.

Strategy modules must not import vectorbt directly.

## Phase 8 - Live NumPy/Numba state

Status: complete.

Implement live stateful indicators under `quant_stack/indicators/live/` and `quant_stack/live/`.

Live tick steps must avoid Polars/dataframe allocation and should be O(1) where possible.

## Phase 9 - Research workflow decoupling

Status: complete.

Move research/discovery/paper context into `quant_stack/research/` and artifacts into `quant_stack/artifacts/`.

LLM output becomes a research artifact, not execution authority.

## Phase 10 - CLI

Status: complete.

Add CLI entry points for backtest, walk-forward, research, and live environment checks.

## Phase 11 - Typed research orchestration boundary

Status: complete.

Implement a strictly typed research orchestration layer in `quant_stack/research/` using Pydantic models and narrow tool wrappers.

Requirements (met):

- Typed schemas for idea, planning, critique, backtest summary, validation report, and queue record/status.
- Queue state machine with explicit allowed transitions and deterministic persistence.
- Guardrails rejecting future-data leaks, broker/live execution paths, and vague non-deterministic strategy definitions.
- Safe tool boundary where research tools can only call strategy registry + deterministic backtesting + validation + artifact store.
- No direct broker/live execution imports or calls from research tool wrappers.
- Focused test suite for schema validation, guards, queue transitions, and boundary constraints.

This phase is additive and does not alter deterministic backtest/live engine semantics.

## Immediate Phase 1 plan

Before moving files, map every import of `engine`, `strategy_families`, `pipeline_artifacts`, `discovery`, `research`, and `live_swarm`. Then create package skeleton and compatibility shims so existing tests can continue importing current paths during migration.

## Phase 12 - Agentic strategy optimizer

Status: complete.

Refactored the old `live_swarm.py` concept into a research-only optimizer under `quant_stack/research/optimization/`.

Delivered:

- Typed request/proposal/critique/objective/run/result schemas.
- Deterministic objective scoring and pass/fail authority (LLM critique is explanatory only).
- Proposal guardrails blocking future-data leaks, live/broker execution requests, backtester semantic tampering, vague logic, and duplicate params.
- Bounded optimization loop that uses strategy registry, safe backtest wrapper, validation, queue, artifacts, and optimization memory.
- No broker/live execution integration and no `strategy_families` coupling.

This phase is additive and does not change backtesting, vectorbt, fill policy, live execution, or broker adapters.
