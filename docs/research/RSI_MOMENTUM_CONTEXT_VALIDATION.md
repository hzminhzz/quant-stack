# Research Document: RSI Momentum Context Filter Validation

## Purpose
Test whether deterministic context/regime filters can improve the risk-adjusted performance of the retained RSI Momentum champion (14/70/30/50).

## Methodology
- **Champion**: Retained from Phase 18B.
- **Filters**: Applied as post-signal gates (Allow/Block).
- **Families**:
    - Volatility (Rolling z-score).
    - Trend Strength (SMA fast/slow).
    - Synthetic Intelligence (Liquidity, Funding).

## Anti-Leakage Rule
All context features are computed using rolling windows or past/current state only. No future information is used to gate signals at any timestamp T.

## Data Source
BTC-USDT 4h data (2018-2026).
Note: Intelligence context (Liquidity/Funding) is currently synthetic/mock and used for pipeline validation only.

## Interpretation
Filters are evaluated by Sharpe improvement, Drawdown reduction, and Trade Retention. A filter candidate is only promoted if it improves risk-adjusted performance without excessive trade reduction.

## Results
Validation artifacts are available in `artifacts/research/btc_4h_rsi_momentum_context_validation_v1/`.
