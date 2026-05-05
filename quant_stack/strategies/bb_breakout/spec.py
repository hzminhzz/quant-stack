"""Bollinger breakout strategy metadata."""

from quant_stack.strategies.specs import StrategySpec

SPEC = StrategySpec(
    name="bb_breakout",
    version="0.1.0",
    timeframe="1h",
    signal_mode="vectorized",
    default_engine="polars",
)

__all__ = ["SPEC"]
