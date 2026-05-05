# Research Document: RSI Momentum Drawdown Attribution (Post-2025-10)

## Objective
Identify the deterministic drivers of the Trend-Filtered RSI Momentum strategy's underperformance starting October 1st, 2025.

## Methodology
- **Diagnostic Period**: 2025-10-01 to Latest.
- **Reference Period**: Start of data to 2025-09-30.
- **Metrics Comparison**: Sharpe, Drawdown, Win Rate, and Profit Factor segments.
- **Attribution Layers**:
    1. **Symbol**: Contribution of BTC, ETH, BNB.
    2. **Direction**: Long vs. Short side contribution.
    3. **Regime**: Volatility, Correlation, and Trend Persistence changes.
    4. **Component**: RSI Signal vs. Trend Filter (SMA 20/50) behavior.

## Anti-Leakage
No parameters are modified. The attribution uses only as-of historical data and frozen rules.

## Classification Labels
- `market_regime_shift_to_chop`: Returns are flat or choppy, whipsaws are frequent.
- `trend_filter_lag_failure`: SMA filter stays long while prices drop, or stays flat during recovery.
- `rsi_signal_failure`: RSI extremes no longer lead to momentum continuation.
- `cost_turnover_drag`: Fees and slippage consume the gross edge.

## Results
Full diagnostic artifacts and the report are available in `artifacts/research/rsi_momentum_post_2025_10_drawdown_attribution_v1/`.
