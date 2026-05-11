"""Research, discovery, paper context, and LLM guardrails."""

from quant_stack.research.discovery import create_strategy_idea
from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.guards import is_generated_code_marked, mark_generated_code_untrusted
from quant_stack.research.llm_generation import build_research_artifact
from quant_stack.research.labeling import TripleBarrierConfig, triple_barrier_labels
from quant_stack.research.model_integration import (
    AssetForecastResult,
    AssetWeightsResult,
    forecast_to_signal_frame,
    run_research_model_backtest,
)
from quant_stack.research.optimization.loop import run_optimization_loop
from quant_stack.research.paper_context import join_paper_context
from quant_stack.research.research import candidate_params
from quant_stack.research.schemas import (
    BacktestSummary,
    CandidateParams,
    ExperimentPlan,
    FeatureIdea,
    RejectionReason,
    ResearchCritique,
    StrategyIdea,
    ValidationReport,
)

__all__ = [
    "BacktestSummary",
    "CandidateParams",
    "ExperimentPlan",
    "ExperimentQueue",
    "FeatureIdea",
    "RejectionReason",
    "ResearchCritique",
    "StrategyIdea",
    "TripleBarrierConfig",
    "AssetForecastResult",
    "AssetWeightsResult",
    "ValidationReport",
    "build_research_artifact",
    "candidate_params",
    "create_strategy_idea",
    "is_generated_code_marked",
    "join_paper_context",
    "mark_generated_code_untrusted",
    "run_optimization_loop",
    "run_research_model_backtest",
    "forecast_to_signal_frame",
    "triple_barrier_labels",
]
