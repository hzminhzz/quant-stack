"""Canonical wrappers for experiment execution workflows."""

from __future__ import annotations

from quant_stack.research.experiments.runner import run_strategy_experiment
from quant_stack.research.experiments.schemas import ExperimentConfig, StrategyComparisonReport

__all__ = ["ExperimentConfig", "StrategyComparisonReport", "run_strategy_experiment"]
