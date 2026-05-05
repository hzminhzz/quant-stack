"""RSI/SMA strategy module factory."""

from quant_stack.strategies.registry import StrategyModule
from quant_stack.strategies.rsi_sma.params import RSISMAParams
from quant_stack.strategies.rsi_sma.signals import build_features, build_signals
from quant_stack.strategies.rsi_sma.spec import SPEC


def strategy_module() -> StrategyModule:
    return StrategyModule(SPEC, RSISMAParams, build_features, build_signals)


__all__ = ["strategy_module"]
