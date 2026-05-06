# Funding Exhaustion Reversal — Comparison Report (Phase 18F)

## 1) Dataset used
None (no executable Bybit feature dataset found).

## 2) Date range
N/A (no eligible dataset selected).

## 3) Feature columns available
Eligible feature set not found.

## 4) Modes tested
Planned but not executed:
- baseline
- context
- context + basis confirmation (conditional on `basis_zscore_60`)

## 5) Parameter configs used
See `config_used.json` (planned configs). No runtime execution occurred.

## 6) Metrics table
No metrics generated because no run was possible.

| mode | total_return | sharpe | max_drawdown | trade_count | win_rate | profit_factor | avg_trade_return | exposure_time | avg_holding_time | worst_trade |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| context | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| context_basis | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

## 7) Baseline vs context comparison
Not computable. No eligible dataset contained required context/baseline feature columns.

## 8) Robustness/falsification results
Not run (depends on successful baseline/context runs).

## 9) Main failure modes
- Missing eligible Bybit feature dataset for `funding_exhaustion_reversal`.
- Scan summary:
  - parquet files discovered in workspace: **111**
  - files matching minimum required feature set (`timestamp,close,symbol,timeframe,rsi_14,funding_zscore_30,momentum_slope_10`): **0**
  - files containing derivative raw columns (`funding_rate/open_interest/basis/...`): **0**

## 10) Verdict
**needs more data**

Rationale: required funding/basis/feature inputs are unavailable in current workspace.

## 11) Recommended next action
Provide or generate (from existing Bybit market dataset) a feature parquet for `BTCUSDT` linear perp at `1m` or `5m` containing at least:
- `timestamp, close, symbol, timeframe, rsi_14, funding_zscore_30, momentum_slope_10, price_extension_20 or ret_60`
- optionally `basis_zscore_60` and `spread_bps`.

After dataset availability, rerun Phase 18F harness for full period, train/test split, and walk-forward (supported in harness) plus robustness checks.
