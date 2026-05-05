# Research Document: RSI Momentum Portfolio Validation

## Objective
Validate the Trend-Filtered RSI Momentum strategy (14/70/30/50 + SMA 20/50) as a multi-asset portfolio across BTC, ETH, and BNB.

## Methodology
- **Assets**: BTC-USDT, ETH-USDT, BNB-USDT (4h).
- **Alignment**: Intersection of valid timestamps across all assets.
- **Construction Variants**:
    1. **Equal Weight Static**: 1/3 allocation to each asset.
    2. **Equal Active Weight**: Dynamic allocation across assets with non-zero signals.
    3. **Volatility Scaled**: Inverse realized volatility weighting (capped).

## Exposure Definitions
- **Gross Exposure**: Sum of absolute weights.
- **Net Exposure**: Sum of weights (directional).

## Anti-Leakage
Portfolio weights at timestamp T are computed using only information available at or before T (e.g., rolling volatility, active signals).

## Results
Portfolio artifacts and the final report are available in `artifacts/research/rsi_momentum_portfolio_validation_v1/`.
