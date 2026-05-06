"""Forced-flow proxy band reclaim strategy metadata."""

from quant_stack.strategies.specs import StrategySpec

SPEC = StrategySpec(
    name="forced_flow_band_reclaim",
    version="0.1.0",
    timeframe="1m",
    signal_mode="vectorized",
    default_engine="polars",
)

__all__ = ["SPEC"]
