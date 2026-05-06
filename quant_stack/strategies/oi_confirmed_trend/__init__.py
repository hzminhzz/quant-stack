"""OI-confirmed trend continuation strategy package."""

from quant_stack.strategies.oi_confirmed_trend.params import OIConfirmedTrendParams
from quant_stack.strategies.oi_confirmed_trend.signals import build_features, build_signals
from quant_stack.strategies.oi_confirmed_trend.spec import SPEC

__all__ = ["OIConfirmedTrendParams", "SPEC", "build_features", "build_signals"]
