# Phase 18F Strategy Experiment: funding_exhaustion_reversal

**Verdict:** inconclusive

## Baseline Metrics
```json
{
  "exposure": 0.0006272401433691756,
  "max_drawdown": -0.05407933782497554,
  "profit_factor": 1.2351365182638359,
  "raw_metrics": {
    "segments": [
      {
        "exposure": 0.0006272401433691756,
        "max_drawdown": -0.05407933782497554,
        "profit_factor": 1.2351365182638359,
        "raw_metrics": {
          "cagr": 0.034234910540521746,
          "cumulative_return": 0.0028629854823791767,
          "gain_pain_ratio": 1.2351365182638492,
          "kelly_criterion": -0.7512520343061151,
          "max_consecutive_losing_days": 1,
          "max_daily_drawdown": -0.05407933782497554,
          "max_drawdown": -0.05407933782497554,
          "smart_sharpe": 0.4996199986441817,
          "smart_sortino": 0.0,
          "tail_ratio": null,
          "time_in_market": 0.0006272401433691756
        },
        "sharpe": 0.4996199986441817,
        "total_return": 0.0028629854823791767,
        "trade_count": 2.0,
        "win_rate": 0.5
      }
    ]
  },
  "sharpe": 0.4996199986441817,
  "total_return": 0.0028629854823791767,
  "trade_count": 2.0,
  "win_rate": 0.5
}
```

## Context Metrics
```json
{
  "exposure": 0.00038082437275985666,
  "max_drawdown": -0.05407933782497554,
  "profit_factor": 0.0,
  "raw_metrics": {
    "segments": [
      {
        "exposure": 0.00038082437275985666,
        "max_drawdown": -0.05407933782497554,
        "profit_factor": 0.0,
        "raw_metrics": {
          "cagr": -0.14354234933270127,
          "cumulative_return": -0.013073664172001731,
          "gain_pain_ratio": 0.0,
          "kelly_criterion": 0.0,
          "max_consecutive_losing_days": 1,
          "max_daily_drawdown": -0.05407933782497554,
          "max_drawdown": -0.05407933782497554,
          "smart_sharpe": -3.4313544772271922,
          "smart_sortino": 0.0,
          "tail_ratio": null,
          "time_in_market": 0.00038082437275985666
        },
        "sharpe": -3.4313544772271922,
        "total_return": -0.013073664172001731,
        "trade_count": 1.0,
        "win_rate": 0.0
      }
    ]
  },
  "sharpe": -3.4313544772271922,
  "total_return": -0.013073664172001731,
  "trade_count": 1.0,
  "win_rate": 0.0
}
```

## Metric Deltas (Context - Baseline)
```json
{
  "exposure": -0.00024641577060931897,
  "max_drawdown": 0.0,
  "profit_factor": -1.2351365182638359,
  "sharpe": -3.930974475871374,
  "total_return": -0.015936649654380908,
  "trade_count": -1.0,
  "win_rate": -0.5
}
```

## Warnings
- context mode exposure is near zero
