# Research Document: RSI Momentum Chop Filter Hypothesis (Phase 18Y)

## Objective
Evaluate whether a secondary deterministic regime gate can mitigate the "Market Regime Shift to Chop" identified in Phase 18X.

## Methodology
- **Baseline**: Trend-Filtered RSI Momentum (14/70/30/50 + SMA 20/50).
- **Candidates**:
    - **Efficiency Ratio (ER)**: Abs Move / Total Path. High ER indicates trending.
    - **Volatility Z-Score**: Realized volatility relative to its own history.
    - **Loss Cooldown**: Temporary entry block after a losing trade.
- **Evaluation Periods**:
    - **Pre-2025-10**: Preservation of historical alpha.
    - **Post-2025-10**: Mitigation of the recent drawdown.
- **Scoring**: Deterministic multi-factor score based on MDD reduction, turnover reduction, and Sharpe preservation.

## Anti-Leakage
Filters are applied as post-signal gates using only information available at the close of bar T.

## Results
Full candidate metrics and the selected filter are available in `artifacts/research/rsi_momentum_chop_filter_hypothesis_v1/`.
