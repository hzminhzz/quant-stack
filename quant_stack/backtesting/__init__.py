"""Backtesting engines, costs, fills, metrics, and result contracts."""

from quant_stack.backtesting.contracts import ValidationContract, ValidationResult, validate_metrics
from quant_stack.backtesting.costs import CostModel
from quant_stack.backtesting.fills import FillPolicy
from quant_stack.backtesting.metrics import calculate_metrics
from quant_stack.backtesting.monte_carlo import run_monte_carlo
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.backtesting.results import BacktestResult
from quant_stack.backtesting.vectorbt_engine import VectorBTBacktester, VectorBTUnavailableError

__all__ = [
    "BacktestResult",
    "CostModel",
    "FillPolicy",
    "PolarsSignalBacktester",
    "ValidationContract",
    "ValidationResult",
    "VectorBTBacktester",
    "VectorBTUnavailableError",
    "calculate_metrics",
    "run_monte_carlo",
    "validate_metrics",
]
