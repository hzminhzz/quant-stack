# Funding Exhaustion Reversal Variant A on XAUUSD

- dataset: `data/XAUUSD.parquet`
- feature parquet: `reports/experiments/funding_exhaustion_reversal/xau_variant_a/xau_features_variant_a.parquet`
- date range: 2017-01-02 23:00:00+00:00 to 2017-10-09 20:19:00+00:00
- rows: 273189

## Params
```json
{
  "basis_zscore_threshold": 1.5,
  "exit_on_rsi_midline": true,
  "exit_rsi_midline": 50.0,
  "funding_zscore_threshold": 2.0,
  "max_spread_bps": null,
  "price_extension_threshold": 0.02,
  "require_basis_confirmation": false,
  "require_momentum_turn": false,
  "require_price_extension": false,
  "rsi_overbought": 70.0,
  "rsi_oversold": 30.0,
  "use_context_filters": false
}
```

## Metrics
```json
{
  "dataset_end": "2017-10-09 20:19:00+00:00",
  "dataset_rows": 273189,
  "dataset_start": "2017-01-02 23:00:00+00:00",
  "exposure": 0.2510276768098276,
  "max_drawdown": -0.021234489770092402,
  "profit_factor": 1.1900621793804798,
  "raw_metrics": {
    "cagr": 0.2549672356015642,
    "cumulative_return": 0.1902357445558016,
    "gain_pain_ratio": 1.9352808990931833,
    "kelly_criterion": 0.2870285108232409,
    "max_consecutive_losing_days": 6,
    "max_daily_drawdown": -0.011806721789223632,
    "max_drawdown": -0.021234489770092402,
    "smart_sharpe": 4.671723041552823,
    "smart_sortino": 6.5947545469027204,
    "tail_ratio": 1.194191382689617,
    "time_in_market": 0.2510276768098276
  },
  "sharpe": 4.671723041552823,
  "total_return": 0.1902357445558016,
  "trade_count": 4894,
  "win_rate": 0.668369431957499
}
```