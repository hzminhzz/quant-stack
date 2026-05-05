# Research Document: RSI Momentum Multi-Symbol Generalization

## Objective
Validate the Trend-Filtered RSI Momentum champion (14/70/30/50 + SMA 20/50) across BTC, ETH, and BNB on the 4h timeframe.

## Methodology
- **Symbols**: BTC-USDT, ETH-USDT, BNB-USDT.
- **Timeframe**: 4h (resampled from 1m).
- **Frozen Strategy**: RSI Momentum (14/70/30/50).
- **Frozen Filter**: Trend Strength Filter (SMA 20/50).
- **Validation**: Per-symbol backtests and walk-forward validation.

## Resampling
- **Method**: Polars `group_by_dynamic`.
- **Aggregation**: OHLCV standard mapping.
- **Anti-Leakage**: Only completed 1m bars are included in each 4h bucket.

## Generalization Score
Deterministic score based on:
1. Positive OOS return on ETH/BNB.
2. Sharpe improvement versus unfiltered champion.
3. Outperforming Buy & Hold Sharpe.

## Results
Multi-symbol artifacts and the final report are available in `artifacts/research/rsi_momentum_multisymbol_generalization_v1/`.
