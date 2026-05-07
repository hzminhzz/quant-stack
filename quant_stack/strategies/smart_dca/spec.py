"""Smart DCA strategy specification."""

from __future__ import annotations

from quant_stack.strategies.specs import StrategySpec, StrategyCapabilities


SPEC = StrategySpec(
    name="smart_dca",
    description="MT5 conversion of DCA Multi Engine v3.1 stateful strategy.",
    version="1.0.0",
    timeframe="1m",
    signal_mode="path_dependent",
    default_engine="grid_dca",
    capabilities=StrategyCapabilities(
        path_dependent=True,
        multi_leg=True,
        average_price_dependent=True,
        supports_vectorized=False,
        requires_bid_ask=True,
        requires_event_log=True,
    ),
)


__all__ = ["SPEC"]
