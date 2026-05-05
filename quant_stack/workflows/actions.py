"""Workflow actions."""

from __future__ import annotations

from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.optimization.schemas import OptimizationRequest
from quant_stack.workflows.schemas import WorkflowDefinition, WorkflowEvent, workflow_request_from_definition


class QueueOptimizationAction:
    """Create and enqueue typed OptimizationRequest records."""

    def __init__(self, queue: ExperimentQueue) -> None:
        self.queue = queue

    def run(
        self,
        definition: WorkflowDefinition,
        event: WorkflowEvent,
        *,
        train_period: str,
        test_period: str,
    ) -> tuple[str, OptimizationRequest]:
        request = workflow_request_from_definition(
            definition,
            event_id=event.event_id,
            train_period=train_period,
            test_period=test_period,
        )

        auto_approve = definition.auto_approve and _is_safe_auto_approval(request)
        record = self.queue.submit_optimization_request(request, auto_approve=auto_approve)
        return record.request_id, request


def _is_safe_auto_approval(request: OptimizationRequest) -> bool:
    # Safety default: only params-only changes can be auto-approved.
    return set(request.allowed_change_types) <= {"params"}


__all__ = ["QueueOptimizationAction"]
