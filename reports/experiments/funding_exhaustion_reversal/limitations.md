# Limitations (Phase 18F funding_exhaustion_reversal run)

1. **Primary blocker: missing dataset**
   - No eligible Bybit feature parquet found containing the required columns for `funding_exhaustion_reversal`.

2. **No backtest execution**
   - Full-period, train/test split, walk-forward, and regime slicing were not run because input data requirements were not met.

3. **No robustness/falsification checks**
   - Delay-by-one-bar, higher costs, threshold perturbations, and filter-disable checks depend on successful base runs.

4. **Cost assumptions not testable**
   - Harness supports fee/slippage inputs, but they were not applied due to no-go state.

5. **Strict-scope compliance**
   - No strategy, backtest engine, feature layer, or live execution code was modified.
