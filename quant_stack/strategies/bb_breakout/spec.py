"""Bollinger breakout strategy metadata."""

from quant_stack.strategies.specs import StrategySpec, StrategyCapabilities

SPEC = StrategySpec(
    name="bb_breakout",
    version="0.1.0",
    timeframe="1h",
    signal_mode="vectorized",
    default_engine="polars",
    capabilities=StrategyCapabilities(
        path_dependent=False,
        multi_leg=False,
        supports_vectorized=True,
    ),
)

__all__ = ["SPEC"]
