"""OI-confirmed trend continuation strategy metadata."""

from quant_stack.strategies.specs import StrategySpec

SPEC = StrategySpec(
    name="oi_confirmed_trend",
    version="0.1.0",
    timeframe="1m",
    signal_mode="vectorized",
    default_engine="polars",
)

__all__ = ["SPEC"]
