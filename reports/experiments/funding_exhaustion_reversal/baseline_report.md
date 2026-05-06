# Funding Exhaustion Reversal — Baseline Mode Report

## Status
**NO-GO (not executed)**

The Phase 18F harness was located and validated, but no dataset in this workspace satisfies the required feature schema for `funding_exhaustion_reversal` baseline execution.

## Required baseline columns
- timestamp
- close
- symbol
- timeframe
- rsi_14
- momentum_slope_10 (required because `require_momentum_turn=True`)
- price_extension_20 **or** ret_60 (required because `require_price_extension=True`)

## Expected baseline params
```json
{
  "use_context_filters": false,
  "require_price_extension": true,
  "require_momentum_turn": true,
  "require_basis_confirmation": false,
  "exit_on_rsi_midline": true
}
```

## Execution note
No baseline backtest was run because required input dataset was missing.
