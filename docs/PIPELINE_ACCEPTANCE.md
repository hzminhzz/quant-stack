# Phase 17 Pipeline Acceptance Harness

The Phase 17 pipeline acceptance harness provides a deterministic end-to-end flow for validating strategy signals and context-gated backtests.

## Workflow Overview

1. **Query Parsing**: Validates the `AcceptanceQuery` YAML which specifies strategy, symbol, timeframe, and context gating rules.
2. **Fixture Preparation**: Generates or loads deterministic OHLCV and intelligence event fixtures.
3. **Signal Generation**: Runs the strategy to produce baseline signals.
4. **Context Gating**: Joins intelligence context (backward-only) and applies gating rules (e.g., spread, imbalance, tags).
5. **Backtesting**: Runs parallel backtests for baseline and context-gated (candidate) signals.
6. **Artifact Creation**: Generates JSON snapshots, validation summaries, and a markdown report.
7. **Optimization Proposal**: Creates a `proposed_only` optimization queue record artifact if requested.

## Usage

Run the harness via the provided script:

```bash
uv run python scripts/run_pipeline_acceptance.py \
    --query examples/pipeline_queries/btc_rsi_sma_context_filter.yaml \
    --output-dir outputs/rsi_sma_run_01

uv run python scripts/run_pipeline_acceptance.py \
    --query examples/pipeline_queries/btc_bb_breakout_context_filter.yaml \
    --output-dir outputs/bb_breakout_run_01
```

### Query Schema (YAML)

```yaml
strategy_name: rsi_sma # or bb_breakout
symbol: BTC
timeframe: 1m # or 1h for bb_breakout
context_gate:
  max_spread_bps: 12.0
  required_context_tags: ["risk_off"]
artifact_mode: proposed_only
```

## Artifact Interpretation

The harness produces the following artifacts in the specified `--output-dir`:

- `acceptance_manifest.json`: Root metadata for the run with normalized non-runtime fields.
- `acceptance_report.md`: Human-readable summary of validation results and performance deltas.
- `validation_summary.json`: Combined validation status and metric deltas.
- `baseline_backtest.json`: Metrics and summary for the ungated strategy signals.
- `candidate_backtest.json`: Metrics and summary for the context-gated strategy signals.
- `joined_context_frame.json`: Full join result verifying no-lookahead context attachment.
- `proposed_optimization.json`: Proposed-only optimization queue record for follow-up tuning, without worker execution.

## Validation Guarantees

- **No-Lookahead**: All backtests enforce `position == target_position.shift(1)`.
- **Backward-Only Join**: Context data is attached using `context_timestamp <= bar_timestamp`.
- **Deterministic**: Fixtures and exported manifest fields avoid runtime timestamps and run-specific absolute paths.
- **Proposed-Only Optimization**: Optimization requests are created as artifacts but never trigger execution.
