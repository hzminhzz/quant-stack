# Research Document: RSI Momentum Robustness Audit

## Hypothesis
RSI extreme values (>70, <30) in crypto act as trend continuation signals rather than mean-reversion signals on the 4h timeframe.

## Audit Methodology
- **Train/Test Split**: 60/40 chronological split.
- **Walk-Forward**: 4 non-overlapping OOS windows (2022-2025).
- **Parameter Sensitivity**: 27-point grid covering period (10-21), entry (65-75), and exit (45-55).
- **Cost Sensitivity**: Analysis from 0bps to 30bps total round-trip costs.
- **Long/Short Attribution**: Returns decomposed by position side.

## Robustness Score Criteria
A score out of 7 is assigned based on:
1. OOS Sharpe > Buy & Hold Sharpe.
2. OOS Max Drawdown < Buy & Hold Max Drawdown.
3. Positive OOS Return after fees.
4. >= 50% profitable walk-forward windows.
5. Broad positive parameter neighborhood.
6. Positive at high cost (10/5 bps).
7. Sufficient trade count.

## Artifacts
The results of this audit are stored in `artifacts/research/btc_4h_rsi_extreme_momentum_robustness_v1/`.
