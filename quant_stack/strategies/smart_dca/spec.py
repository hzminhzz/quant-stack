"""Smart DCA strategy specification."""

from __future__ import annotations

from quant_stack.strategies.specs import StrategySpec


SPEC = StrategySpec(
    name="smart_dca",
    description="MT5 conversion of DCA Multi Engine v3.1 stateful strategy.",
    version="1.0.0",
    timeframe="1m",
    signal_mode="path_dependent",
    default_engine="vectorbt",
)


__all__ = ["SPEC"]
