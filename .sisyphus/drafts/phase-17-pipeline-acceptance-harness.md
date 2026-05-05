# Draft: Phase 17 Pipeline Acceptance Harness

## Requirements (confirmed)
- Execute Phase 17 only.
- Create `examples/pipeline_queries/` YAMLs, `scripts/run_pipeline_acceptance.py`, `tests/e2e/test_pipeline_acceptance.py`, and `docs/PIPELINE_ACCEPTANCE.md`.
- Prove deterministic pipeline flow: data -> indicators -> strategy signals -> backtest -> intelligence context join -> validation -> optional OptimizationRequest artifact.
- Do not add new strategy logic.
- Do not improve optimizer.
- Do not add live trading.
- Do not modify broker/execution/risk modules.
- Do not require OKX credentials or any real API credentials.
- Do not use pandas in core.

## Technical Decisions
- Candidate vs baseline: same strategy, params, OHLCV, and backtest engine; candidate differs only by a post-strategy, pre-backtest context gating/filter layer.
- Join target: timestamped bar-level backtest/signal frame, never `BacktestResult.trades`.
- Strategy scope: `rsi_sma` and `bb_breakout` only; explicitly exclude `grid`.
- Intelligence context source: deterministic mock `SignalEvent` fixtures written/read through `quant_stack.intelligence.store`.
- Optional optimization artifact: create `OptimizationRequest` JSON and enqueue it in proposed state only; never invoke optimizer worker.
- Validation contract: use existing `validate_metrics` contract plus explicit acceptance assertions for no-lookahead and no-future-leakage.

## Research Findings
- `quant_stack.data` provides validated OHLCV loading/resampling/normalization.
- `PolarsSignalBacktester` already enforces `shift(1)` no-lookahead semantics.
- `quant_stack.intelligence.snapshot.join_context_to_trades` uses backward as-of semantics and honors `historical_integrity`.
- No existing YAML pipeline loader or acceptance harness exists in repo.
- Workflow/optimization queue already supports proposed optimization requests and separate worker execution.

## Open Questions
- None blocking; defaults applied from repository constraints.

## Scope Boundaries
- INCLUDE: deterministic fixtures, YAML query parsing, context gating harness, artifact/report writing, proposed optimization request artifact.
- EXCLUDE: optimizer execution, live data/API credentials, broker/live/risk modules, new strategy formulas, grid strategy support.
