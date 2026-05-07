"""Smart DCA strategy package."""

from quant_stack.strategies.smart_dca.adapter import prepare_from_polars, run_smart_dca_backtest
from quant_stack.strategies.smart_dca.backtester import SmartDCABacktester
from quant_stack.strategies.smart_dca.module import strategy_module
from quant_stack.strategies.smart_dca.params import EngineConfig, SmartDCAParams
from quant_stack.strategies.smart_dca.signals import build_features, build_signals
from quant_stack.strategies.smart_dca.simulator import simulate_smart_dca
from quant_stack.strategies.smart_dca.spec import SPEC

__all__ = [
    "EngineConfig",
    "SmartDCABacktester",
    "SmartDCAParams",
    "SPEC",
    "build_features",
    "build_signals",
    "prepare_from_polars",
    "run_smart_dca_backtest",
    "simulate_smart_dca",
    "strategy_module",
]
