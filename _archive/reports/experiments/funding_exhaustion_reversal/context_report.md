# Funding Exhaustion Reversal — Context Mode Report

## Status
**NO-GO (not executed)**

No Bybit feature dataset in this workspace contains the required context feature set for `funding_exhaustion_reversal` context execution.

## Required context columns
- timestamp
- close
- symbol
- timeframe
- rsi_14
- funding_zscore_30
- momentum_slope_10
- price_extension_20 **or** ret_60

## Basis-confirmation add-on requirement
If `require_basis_confirmation=True`, additional required column:
- basis_zscore_60

## Expected context params
```json
{
  "use_context_filters": true,
  "funding_zscore_threshold": 2.0,
  "require_price_extension": true,
  "require_momentum_turn": true,
  "require_basis_confirmation": false,
  "exit_on_rsi_midline": true
}
```

## Expected context+basis params (only when basis_zscore_60 exists)
```json
{
  "use_context_filters": true,
  "funding_zscore_threshold": 2.0,
  "require_basis_confirmation": true,
  "basis_zscore_threshold": 1.5,
  "require_price_extension": true,
  "require_momentum_turn": true
}
```

## Execution note
No context or context+basis backtests were run because required feature columns were unavailable.
