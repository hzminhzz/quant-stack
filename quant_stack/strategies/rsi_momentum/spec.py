"""RSI Momentum strategy specification."""

from __future__ import annotations
from quant_stack.strategies.specs import StrategySpec

def get_spec() -> StrategySpec:
    return StrategySpec(
        name="rsi_momentum",
        version="1.0.0",
        timeframe="4h",
        signal_mode="vectorized",
        default_engine="polars"
    )
