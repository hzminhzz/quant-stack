"""Bounded research-only optimization loop."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from quant_stack.artifacts.store import save_artifact
from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.optimization.guards import guard_patch_proposal
from quant_stack.research.optimization.memory import OptimizationMemory
from quant_stack.research.optimization.objective import score_objective
from quant_stack.research.optimization.schemas import (
    BacktestCritique,
    OptimizationCandidate,
    OptimizationRequest,
    OptimizationResult,
    OptimizationRun,
    StrategyPatchProposal,
)
from quant_stack.research.schemas import BacktestSummary, CandidateParams, ExperimentPlan, ExperimentStatus, ValidationReport
from quant_stack.research.tools import request_backtest_from_plan
from quant_stack.strategies import available_strategies


class OptimizerAgentProtocol(Protocol):
    async def propose(
        self,
        *,
        request: OptimizationRequest,
        latest_summary: BacktestSummary,
        critique: BacktestCritique,
        prior_params: list[dict[str, object]],
    ) -> StrategyPatchProposal: ...


class CriticAgentProtocol(Protocol):
    async def critique(self, *, summary: BacktestSummary, validation: ValidationReport) -> BacktestCritique: ...


def _build_plan(request: OptimizationRequest, params: dict[str, object], acceptance_criteria: list[str]) -> ExperimentPlan:
    return ExperimentPlan(
        strategy_name=request.strategy_name,
        params_to_test=[CandidateParams(strategy_name=request.strategy_name, params=params, rationale="optimizer proposal")],
        symbols=request.symbols,
        timeframes=request.timeframes,
        train_period=request.train_period,
        test_period=request.test_period,
        validation_method="walk-forward",
        acceptance_criteria=acceptance_criteria,
    )


def _summary_to_validation(summary: BacktestSummary) -> ValidationReport:
    passed = summary.pass_fail == "pass"
    return ValidationReport(
        passed=passed,
        reasons=list(summary.major_weaknesses),
        metrics=dict(summary.metrics),
        risk_flags=list(summary.major_weaknesses),
        artifact_path=summary.artifact_path,
    )


async def run_optimization_loop(
    request: OptimizationRequest,
    *,
    optimizer: OptimizerAgentProtocol,
    critic: CriticAgentProtocol,
    queue_path: str | Path,
    memory_path: str | Path,
    artifact_dir: str | Path = "artifacts/research/optimization",
) -> OptimizationResult:
    if request.strategy_name not in set(available_strategies()):
        raise ValueError(f"unknown strategy: {request.strategy_name}")

    run_id = f"opt-{uuid4().hex}"
    run = OptimizationRun(run_id=run_id, request=request)
    queue = ExperimentQueue(queue_path)
    memory = OptimizationMemory(memory_path, run_id=run_id)
    acceptance_lines = [
        f"min_trades={request.acceptance_criteria.min_trades}",
        f"min_oos_sharpe={request.acceptance_criteria.min_oos_sharpe}",
        f"max_drawdown={request.acceptance_criteria.max_drawdown}",
    ]

    baseline_plan = _build_plan(request, params={}, acceptance_criteria=acceptance_lines)
    baseline_summary = request_backtest_from_plan(baseline_plan)
    baseline_validation = _summary_to_validation(baseline_summary)
    baseline_score = score_objective(baseline_summary, baseline_validation, request.acceptance_criteria)
    baseline_critique = await critic.critique(summary=baseline_summary, validation=baseline_validation)

    best_candidate: OptimizationCandidate | None = None
    best_score_value = float("-inf")
    latest_summary = baseline_summary
    latest_critique = baseline_critique

    for iteration in range(request.max_iterations):
        proposal = await optimizer.propose(
            request=request,
            latest_summary=latest_summary,
            critique=latest_critique,
            prior_params=[candidate.proposal.params for candidate in run.candidates],
        )
        candidate_id = f"cand-{iteration + 1}"
        candidate = OptimizationCandidate(candidate_id=candidate_id, proposal=proposal)

        guard_reasons = guard_patch_proposal(
            proposal,
            allowed_change_types=set(request.allowed_change_types),
            tested_param_fingerprints=memory.tested_param_fingerprints(),
        )
        if guard_reasons:
            candidate.status = "skipped" if any(reason.code == "duplicate_params" for reason in guard_reasons) else "rejected"
            candidate.rejection_reason = guard_reasons[0]
            run.candidates.append(candidate)
            memory.add_candidate(candidate)
            continue

        plan = _build_plan(request, params=proposal.params, acceptance_criteria=acceptance_lines)
        record = queue.submit(plan, created_by_agent="optimizer")
        queue.transition(record.experiment_id, ExperimentStatus.APPROVED)
        queue.transition(record.experiment_id, ExperimentStatus.RUNNING)

        summary = request_backtest_from_plan(plan)
        validation = _summary_to_validation(summary)
        objective = score_objective(summary, validation, request.acceptance_criteria)

        candidate.status = "completed"
        candidate.result_path = summary.artifact_path
        candidate.score = objective
        run.candidates.append(candidate)
        memory.add_candidate(candidate)

        if objective.passed:
            queue.transition(record.experiment_id, ExperimentStatus.COMPLETED, result_path=summary.artifact_path)
        else:
            queue.transition(record.experiment_id, ExperimentStatus.FAILED, result_path=summary.artifact_path)

        latest_summary = summary
        latest_critique = await critic.critique(summary=summary, validation=validation)

        if objective.score > best_score_value:
            best_score_value = objective.score
            best_candidate = candidate

        if objective.passed:
            run.best_candidate_id = candidate.candidate_id
            run.status = "approved"
            break
    else:
        run.status = "rejected"

    if best_candidate is None:
        baseline_candidate = OptimizationCandidate(
            candidate_id="baseline",
            proposal=StrategyPatchProposal(
                strategy_name=request.strategy_name,
                change_type="params",
                params={},
                rationale="baseline run",
                expected_effect="reference",
                risks=[],
            ),
            status="completed",
            result_path=baseline_summary.artifact_path,
            score=baseline_score,
        )
        best_candidate = baseline_candidate

    run.completed_at = datetime.now(timezone.utc)
    artifact_root = Path(artifact_dir)
    artifact_path = artifact_root / f"{run_id}.json"
    result = OptimizationResult(
        run_id=run_id,
        best_candidate=best_candidate,
        best_score=best_candidate.score,
        approved=bool(best_candidate.score and best_candidate.score.passed),
        summary=("approved" if (best_candidate.score and best_candidate.score.passed) else "rejected after bounded iterations"),
        artifact_path=artifact_path.as_posix(),
    )
    save_artifact(run, artifact_root / f"{run_id}_run.json")
    save_artifact(result, artifact_path)
    return result


__all__ = ["run_optimization_loop"]
