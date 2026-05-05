# Research Document: RSI Momentum Holdout Validation (Phase 18Z)

## Objective
Validate the `high_volatility_disable` chop filter on independent assets and forward data to confirm generalization and rule out local overfitting.

## Methodology
- **Holdout Assets**: SOL-USDT, ADA-USDT (Unseen during filter selection).
- **Forward Data**: 2026-01-01 to Latest (BTC, ETH, BNB).
- **Comparison**: 
    - **Baseline**: Phase 18C Champion (RSI 14/70/30/50 + SMA 20/50).
    - **Enhanced**: Baseline + `high_volatility_disable` (Threshold 2.5).
- **Metric**: Smart Sharpe, Max Drawdown, and MDD Improvement.

## Anti-Leakage
- SOL and ADA data were not used for filter selection or parameter tuning.
- Forward data (2026) was not used in Phase 18X or 18Y analysis.

## Success Criteria
- **VALIDATED**: Enhanced candidate outperforms Baseline on average across holdout assets.
- **FAILED**: Enhanced candidate underperforms Baseline on average across holdout assets.

## Results
Full holdout metrics and the validation report are available in `artifacts/research/rsi_momentum_holdout_validation_v1/`.
