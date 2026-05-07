# Phase 18F.1: Funding Exhaustion Reversal Signal Coverage Calibration

## 1. Dataset and Date Range
- **Dataset:** `data/features/bybit/BTCUSDT/1m/features.parquet`
- **Date Range:** 2024-01-01T00:00:00+00:00 to 2024-03-01T00:00:00+00:00

## 2. All Variants Tested
- Variant A — RSI-only baseline
- Variant E — RSI + loose funding
- Variant F — RSI + medium funding
- Variant C — RSI + momentum turn
- Variant H — RSI + loose funding + momentum turn
- Variant B — RSI + price extension
- Variant G — RSI + loose funding + price extension
- Variant D — RSI + extension + momentum

## 3. Metrics Table
| ID | Variant | Trade Count | Exposure | Total Return | Max Drawdown | Sharpe | Win Rate | Avg Trade | Profit Factor |
|---|---|---|---|---|---|---|---|---|---|
| A | Variant A — RSI-only baseline | 803 | 23.8956% | -19.39% | -20.19% | -9.80 | 72% | 0.03% | 0.24 |
| E | Variant E — RSI + loose funding | 418 | 12.3230% | -11.77% | -13.08% | -6.82 | 72% | 0.03% | 0.32 |
| F | Variant F — RSI + medium funding | 417 | 12.3073% | -11.91% | -13.21% | -6.88 | 72% | 0.03% | 0.32 |
| C | Variant C — RSI + momentum turn | 382 | 9.0681% | -10.08% | -10.60% | -7.45 | 73% | 0.03% | 0.33 |
| H | Variant H — RSI + loose funding + momentum turn | 111 | 2.4619% | -2.79% | -6.42% | -3.17 | 75% | 0.03% | 0.58 |
| B | Variant B — RSI + price extension | 16 | 0.5981% | 4.23% | -7.40% | 2.31 | 62% | 0.33% | 1.80 |
| G | Variant G — RSI + loose funding + price extension | 7 | 0.3181% | -4.72% | -7.40% | -4.71 | 43% | -0.62% | 0.11 |
| D | Variant D — RSI + extension + momentum | 4 | 0.1725% | -1.06% | -5.44% | -1.56 | 25% | -0.20% | 0.60 |

## 4. Trade-count Ranking
1. Variant A — RSI-only baseline (803 trades)
2. Variant E — RSI + loose funding (418 trades)
3. Variant F — RSI + medium funding (417 trades)
4. Variant C — RSI + momentum turn (382 trades)
5. Variant H — RSI + loose funding + momentum turn (111 trades)
6. Variant B — RSI + price extension (16 trades)
7. Variant G — RSI + loose funding + price extension (7 trades)
8. Variant D — RSI + extension + momentum (4 trades)

## 5. Which variants reached >=30 trades
- Variant A — RSI-only baseline (803 trades)
- Variant E — RSI + loose funding (418 trades)
- Variant F — RSI + medium funding (417 trades)
- Variant C — RSI + momentum turn (382 trades)
- Variant H — RSI + loose funding + momentum turn (111 trades)

## 6. Which variants reached >=50 trades
- Variant A — RSI-only baseline (803 trades)
- Variant E — RSI + loose funding (418 trades)
- Variant F — RSI + medium funding (417 trades)
- Variant C — RSI + momentum turn (382 trades)
- Variant H — RSI + loose funding + momentum turn (111 trades)

## 7. Whether funding filter improves or only suppresses trades
The RSI-only baseline (A) generated 803 trades. Adding loose funding (E) generated 418 trades. The funding filter reduces trades but maintains a viable sample size.

## 8. Recommended candidate variant for real validation
Recommended: Variant E — RSI + loose funding
Reason: Meets the trade count threshold (418) with acceptable drawdown (-13.08%).

## 9. Recommended next test window
Next step is to run the recommended candidate on a subsequent holdout period (e.g. 2024-03-01 to 2024-05-01) to validate edge robustness.
