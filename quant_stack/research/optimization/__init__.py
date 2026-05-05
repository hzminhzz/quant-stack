"""Phase 12 research-only strategy optimization package."""

from quant_stack.research.optimization.critic import OptimizerCriticAgent
from quant_stack.research.optimization.guards import guard_patch_proposal, params_fingerprint
from quant_stack.research.optimization.loop import run_optimization_loop
from quant_stack.research.optimization.memory import OptimizationMemory, OptimizationMemorySnapshot
from quant_stack.research.optimization.objective import DEFAULT_WEIGHTS, score_objective
from quant_stack.research.optimization.optimizer_agent import StrategyOptimizerAgent
from quant_stack.research.optimization.worker import OptimizationWorker
from quant_stack.research.optimization.schemas import (
    AcceptanceCriteria,
    BacktestCritique,
    ObjectiveScore,
    OptimizationCandidate,
    OptimizationRequest,
    OptimizationResult,
    OptimizationRun,
    RejectionReason,
    StrategyPatchProposal,
)

__all__ = [
    "AcceptanceCriteria",
    "BacktestCritique",
    "DEFAULT_WEIGHTS",
    "ObjectiveScore",
    "OptimizationCandidate",
    "OptimizationMemory",
    "OptimizationMemorySnapshot",
    "OptimizationRequest",
    "OptimizationResult",
    "OptimizationRun",
    "OptimizerCriticAgent",
    "OptimizationWorker",
    "RejectionReason",
    "StrategyOptimizerAgent",
    "StrategyPatchProposal",
    "guard_patch_proposal",
    "params_fingerprint",
    "run_optimization_loop",
    "score_objective",
]
