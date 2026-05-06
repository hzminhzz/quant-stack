"""Phase 18F strategy experiment harness."""

from quant_stack.research.experiments.comparison import compare_results
from quant_stack.research.experiments.config import build_mode_params, load_params_json
from quant_stack.research.experiments.report import render_comparison_markdown
from quant_stack.research.experiments.runner import run_strategy_experiment
from quant_stack.research.experiments.schemas import (
    ExperimentConfig,
    StrategyComparisonReport,
    StrategyExperimentResult,
)

__all__ = [
    "ExperimentConfig",
    "StrategyComparisonReport",
    "StrategyExperimentResult",
    "build_mode_params",
    "compare_results",
    "load_params_json",
    "render_comparison_markdown",
    "run_strategy_experiment",
]
