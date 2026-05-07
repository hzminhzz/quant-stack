"""Smart DCA strategy module factory."""

from quant_stack.strategies.smart_dca.params import SmartDCAParams
from quant_stack.strategies.smart_dca.signals import build_features, build_signals
from quant_stack.strategies.smart_dca.spec import SPEC
from quant_stack.strategies.registry import StrategyModule


def strategy_module() -> StrategyModule:
    return StrategyModule(SPEC, SmartDCAParams, build_features, build_signals)


__all__ = ["strategy_module"]
