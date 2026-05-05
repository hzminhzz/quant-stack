"""RSI Momentum strategy module definition."""

from quant_stack.strategies.registry import StrategyModule
from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams
from quant_stack.strategies.rsi_momentum.spec import get_spec
from quant_stack.strategies.rsi_momentum.signals import build_features, build_signals

def strategy_module() -> StrategyModule:
    return StrategyModule(
        spec=get_spec(),
        params_model=RSIMomentumParams,
        build_features=build_features,
        build_signals=build_signals
    )
