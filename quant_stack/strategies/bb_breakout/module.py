"""Bollinger breakout strategy module factory."""

from quant_stack.strategies.bb_breakout.params import BBBreakoutParams
from quant_stack.strategies.bb_breakout.signals import build_features, build_signals
from quant_stack.strategies.bb_breakout.spec import SPEC
from quant_stack.strategies.registry import StrategyModule


def strategy_module() -> StrategyModule:
    return StrategyModule(SPEC, BBBreakoutParams, build_features, build_signals)


__all__ = ["strategy_module"]
