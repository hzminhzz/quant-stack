"""RSI/SMA strategy metadata."""

from quant_stack.strategies.specs import StrategySpec

SPEC = StrategySpec(
    name="rsi_sma",
    version="0.1.0",
    timeframe="1m",
    signal_mode="vectorized",
    default_engine="polars",
)

__all__ = ["SPEC"]
