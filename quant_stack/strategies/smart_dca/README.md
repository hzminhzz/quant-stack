# Smart DCA Strategy

This is an MT5 EA conversion (DCA Multi Engine v3.1).

It simulates a stateful Grid/DCA system with 4 deterministic engines:
- SB (Slow Buy)
- FB (Fast Buy)
- SS (Slow Sell)
- FS (Fast Sell)

## Integration
Since this strategy heavily depends on state (MT5 BuildStates, path-dependent orders, dynamic TP), it does not strictly adhere to stateless signal generation like RSI or Moving Average strategies. It instead relies on a deterministic core simulator implemented in NumPy for max performance.

## Example usage

```python
import polars as pl
from quant_stack.strategies.smart_dca import SmartDCAParams, run_smart_dca_backtest

# Load 1m canonical data
df = pl.read_parquet("data/XAUUSD_1m.parquet")

# Must compute bid/ask if they are missing
if "bid" not in df.columns:
    df = df.with_columns(
        pl.col("close").alias("bid"),
        pl.col("close").alias("ask")  # naive 0 spread fallback
    )

cfg = SmartDCAParams(
    use_bid_as_avr=True,
    contract_size=1.0,
    commission_per_lot=0.0,
)

# Run the deterministic state machine
results = run_smart_dca_backtest(df, cfg)

print(results["equity"][-1])
print(len(results["trade_time_idx"]), "trades executed")
```
