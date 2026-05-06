# Phase 19 Autonomous Research Pipeline Orchestration

## Purpose

This document describes the automated Phase 19 research pipeline for MACD-TD V6 strategy validation. The orchestrator runs subphases sequentially with deterministic gates, stopping immediately if any gate fails.

## Subphase Sequence

| Phase | Name | Gate Function | Artifact Root |
|-------|------|---------------|---------------|
| 19B | Deterministic Prototype | `gate_19b` | `macd_td_v6_prototype_v1` |
| 19C | Economic Validation | `gate_19c` | `macd_td_v6_economic_validation_v1` |
| 19D | Robustness Audit | `gate_19d` | `macd_td_v6_robustness_v1` |
| 19E | Sensitivity Analysis | `gate_19e` | `macd_td_v6_sensitivity_v1` |
| 19F | Candidate Comparison | `gate_19f` | `macd_td_v6_candidate_comparison_v1` |

## Gate Definitions

### Phase 19B Gate (Deterministic Prototype)
- **Required artifacts**: `prototype_config.json`, `data_coverage_summary.json`, `trade_log.json`, `equity_curve.json`, `prototype_metrics.json`, `leakage_fix_verification.json`, `eligibility_report.json`
- **Pass conditions**:
  - All artifacts exist
  - `same_bar_execution_removed = true`
  - `nearest_timestamp_replaced = true`
  - `extrema_confirmation_delay_enforced = true`
  - `future_alignment_count = 0`
  - `pandas_used_in_core_path = false`
  - Eligibility verdict is `eligible_for_economic_validation` or `eligible_with_remaining_risks`

### Phase 19C Gate (Economic Validation)
- **Required artifacts**: `symbol_metrics.json`, `economic_validation_score.json`, `eligibility_report.json`
- **Pass conditions**:
  - All artifacts exist
  - Score classification is `promising` or `mixed`
  - At least one symbol has ≥10 trades

### Phase 19D Gate (Robustness Audit)
- **Required artifacts**: `robustness_score.json`, `walk_forward_metrics.json`, `cost_sensitivity.json`, `eligibility_report.json`
- **Pass conditions**:
  - Classification is `robust` or `promising_but_fragile`
  - Not catastrophic at normal costs

### Phase 19E Gate (Sensitivity Analysis)
- **Required artifacts**: `sensitivity_score.json`, `selected_research_candidate.json`, `eligibility_report.json`
- **Pass conditions**:
  - Classification is `keep_baseline` or `stable_alternative_found`
  - Not `rejected` or `fragile_needs_more_data`

### Phase 19F Gate (Candidate Comparison)
- **Required artifacts**: `final_research_decision.json`, `macd_td_candidate_metrics.json`, `rsi_momentum_candidate_metrics.json`
- **Pass conditions**:
  - Decision exists and pipeline completes

## Stop Conditions

The pipeline stops immediately if:
- Tests fail
- Required artifacts are missing
- Future timestamp alignment count > 0
- Same-bar entry still exists
- Extrema confirmation delay not enforced
- Pandas imported in core/prototype path
- TA-Lib required
- Live API required
- Broker/account/order module imported
- Optimizer called outside allowed bounded sensitivity
- Eligibility verdict is `not_eligible`

## Artifacts

### Pipeline Artifacts
- `phase19_status.json` - Pipeline status
- `phase19_decision_log.json` - Ordered decision log
- `phase19_summary.json` - Summary
- `phase19_final_report.md` - Final report

### Per-Phase Artifacts
Each phase produces its own artifacts in the corresponding subdirectory under `artifacts/research/`.

## How to Run

```bash
# Run the autonomous pipeline
python scripts/run_phase19_macd_td_auto.py examples/pipeline_queries/phase19_macd_td_auto.yaml

# Or with uv
uv run python scripts/run_phase19_macd_td_auto.py examples/pipeline_queries/phase19_macd_td_auto.yaml
```

## How to Resume After Failure

1. Check `phase19_status.json` for failure reason
2. Check `phase19_decision_log.json` for gate details
3. Fix the issue in the failed phase's artifacts
4. Re-run the pipeline

## What Automation Is Allowed

- **Allowed**: Deterministic research execution, gate evaluation, artifact generation
- **Allowed**: Running subphases sequentially with no human prompts
- **Allowed**: Stopping on gate failures

## What Automation Is Forbidden

- **Forbidden**: Production deployment
- **Forbidden**: Paper trading or live trading
- **Forbidden**: Modifying live execution, risk, broker modules
- **Forbidden**: Running unbounded optimization
- **Forbidden**: Changing strategy rules to improve results (unless explicitly allowed in subphase)
- **Forbidden**: Skipping gates or continuing after failures
- **Forbidden**: Auto-approving production deployment

## Why This Does Not Enable Production/Live Trading

1. **Research-only scope**: Pipeline is confined to `quant_stack/research/` modules
2. **No broker integration**: No import of `broker`, `account`, `order` modules
3. **No live execution**: Pipeline uses local/synthetic data only
4. **No production approval**: Final decision is a research recommendation only
5. **Strict gates**: Pipeline stops on any failure, not pushing through for "good enough" results
6. **No deployment automation**: No scripts to enable paper trading or live trading from pipeline output

## Files Created

- `quant_stack/research/phase_orchestration/__init__.py`
- `quant_stack/research/phase_orchestration/gates.py`
- `quant_stack/research/phase_orchestration/phase_status.py`
- `quant_stack/research/phase_orchestration/phase19_runner.py`
- `examples/pipeline_queries/phase19_macd_td_auto.yaml`
- `scripts/run_phase19_macd_td_auto.py`
- `tests/research/test_phase19_auto_orchestration.py`
- `docs/research/PHASE19_MACD_TD_AUTO_ORCHESTRATION.md`