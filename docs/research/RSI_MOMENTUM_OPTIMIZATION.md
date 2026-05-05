# Research Document: RSI Momentum Parameter Optimization

## Objective
Identify the most robust and high-performing parameter set for the BTC-USDT 4h RSI Momentum strategy using a deterministic grid search.

## Search Space
- **RSI Period**: [7, 10, 14, 18, 21, 28]
- **RSI Upper**: [65, 70, 75, 80]
- **RSI Lower**: [20, 25, 30, 35]
- **RSI Exit**: [45, 50, 55]

## Constraints
1. `rsi_upper > rsi_exit`
2. `rsi_lower < rsi_exit`
3. `rsi_upper - rsi_lower >= 25`

## Validation Method
- **Train (60%)**: Earliest period used for initial backtesting.
- **Validation (25%)**: Period used for candidate selection via objective scoring.
- **Holdout (15%)**: Final isolated period for "Champion vs Challenger" evaluation.

## Objective Function
The objective score combines risk-adjusted returns (Sharpe), total returns, and stability (Max Drawdown), with penalties for overfitting (IS/OOS gap) and high drawdown.

## Results
Optimization artifacts and the final report are available in `artifacts/research/btc_4h_rsi_extreme_momentum_optimization_v1/`.
