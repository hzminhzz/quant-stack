"""Queue consumer worker for optimization requests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from quant_stack.research.experiment_queue import ExperimentQueue, OptimizationRequestStatus
from quant_stack.research.optimization.critic import OptimizerCriticAgent
from quant_stack.research.optimization.loop import run_optimization_loop
from quant_stack.research.optimization.optimizer_agent import StrategyOptimizerAgent
from quant_stack.research.schemas import RejectionReason


class OptimizationWorker:
    def __init__(
        self,
        *,
        queue_path: str | Path,
        memory_root: str | Path = "artifacts/research/optimization/memory",
        artifact_dir: str | Path = "artifacts/research/optimization",
        optimizer_model: object | None = None,
        critic_model: object | None = None,
    ) -> None:
        self.queue = ExperimentQueue(queue_path)
        self.memory_root = Path(memory_root)
        self.artifact_dir = Path(artifact_dir)
        self.optimizer_model = optimizer_model
        self.critic_model = critic_model

    def run_once(self) -> str | None:
        approved = self.queue.list_optimization_requests(status=OptimizationRequestStatus.APPROVED)
        if not approved:
            return None
        record = approved[0]
        request = record.request

        if set(request.allowed_change_types) - {"params", "features"}:
            self.queue.transition_optimization_request(
                record.request_id,
                OptimizationRequestStatus.REJECTED,
                rejection_reason=RejectionReason(
                    code="unsafe_auto_approved_change_type",
                    message="workflow auto-approved request includes unsafe change type",
                    severity="high",
                ),
            )
            return None

        self.queue.transition_optimization_request(record.request_id, OptimizationRequestStatus.RUNNING)
        memory_path = self.memory_root / f"{record.request_id}.json"

        try:
            result = asyncio.run(
                run_optimization_loop(
                    request,
                    optimizer=StrategyOptimizerAgent(self.optimizer_model),
                    critic=OptimizerCriticAgent(self.critic_model),
                    queue_path=self.queue.path,
                    memory_path=memory_path,
                    artifact_dir=self.artifact_dir,
                )
            )
            terminal = OptimizationRequestStatus.COMPLETED if result.approved else OptimizationRequestStatus.FAILED
            self.queue.transition_optimization_request(record.request_id, terminal, result_path=result.artifact_path)
            return result.artifact_path
        except Exception as exc:  # pragma: no cover - defensive terminal write
            self.queue.transition_optimization_request(
                record.request_id,
                OptimizationRequestStatus.FAILED,
                result_path=str(exc),
            )
            raise


__all__ = ["OptimizationWorker"]
