"""Grid strategy metadata."""

from quant_stack.strategies.specs import StrategySpec

SPEC = StrategySpec(
    name="grid",
    version="0.1.0",
    timeframe="1m",
    signal_mode="path_dependent",
    default_engine="vectorbt",
)

__all__ = ["SPEC"]
