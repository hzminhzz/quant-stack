"""RSI/SMA strategy metadata."""

from quant_stack.strategies.specs import StrategySpec, StrategyCapabilities

SPEC = StrategySpec(
    name="rsi_sma",
    version="0.1.0",
    timeframe="1m",
    signal_mode="vectorized",
    default_engine="polars",
    capabilities=StrategyCapabilities(
        path_dependent=False,
        multi_leg=False,
        average_price_dependent=False,
        supports_vectorized=True,
        requires_bid_ask=False,
    ),
)

__all__ = ["SPEC"]
