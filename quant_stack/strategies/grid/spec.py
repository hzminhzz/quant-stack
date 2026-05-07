"""Grid strategy metadata."""

from quant_stack.strategies.specs import StrategySpec, StrategyCapabilities

SPEC = StrategySpec(
    name="grid",
    version="0.1.0",
    timeframe="1m",
    signal_mode="path_dependent",
    default_engine="grid_dca",
    capabilities=StrategyCapabilities(
        path_dependent=True,
        multi_leg=True,
        average_price_dependent=True,
        supports_vectorized=False,
    ),
)

__all__ = ["SPEC"]
