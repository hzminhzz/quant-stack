"""Workflow engine that handles events and enqueues optimization requests."""

from __future__ import annotations

from quant_stack.workflows.actions import QueueOptimizationAction
from quant_stack.workflows.cooldown import CooldownStore
from quant_stack.workflows.registry import WorkflowRegistry
from quant_stack.workflows.schemas import WorkflowDecision, WorkflowEvent
from quant_stack.workflows.triggers import ContextTagTrigger


class WorkflowEngine:
    """Event router that never calls optimizer loop directly."""

    def __init__(
        self,
        *,
        registry: WorkflowRegistry,
        trigger: ContextTagTrigger,
        action: QueueOptimizationAction,
        cooldown_store: CooldownStore,
    ) -> None:
        self.registry = registry
        self.trigger = trigger
        self.action = action
        self.cooldown_store = cooldown_store

    def handle_event(self, event: WorkflowEvent, *, train_period: str, test_period: str) -> list[WorkflowDecision]:
        decisions: list[WorkflowDecision] = []
        for definition in self.registry.list_enabled():
            cooldown_key = f"{definition.workflow_id}:{event.symbol}:{event.timeframe}"
            if self.cooldown_store.is_on_cooldown(cooldown_key, cooldown_seconds=definition.cooldown_seconds, now=event.timestamp):
                decisions.append(
                    WorkflowDecision(
                        workflow_id=definition.workflow_id,
                        event_id=event.event_id,
                        triggered=False,
                        reason="cooldown_active",
                    )
                )
                continue

            if not self.trigger.should_fire(definition, event):
                decisions.append(
                    WorkflowDecision(
                        workflow_id=definition.workflow_id,
                        event_id=event.event_id,
                        triggered=False,
                        reason="missing_required_context_tags",
                    )
                )
                continue

            request_id, _ = self.action.run(definition, event, train_period=train_period, test_period=test_period)
            self.cooldown_store.mark_triggered(cooldown_key, now=event.timestamp)
            decisions.append(
                WorkflowDecision(
                    workflow_id=definition.workflow_id,
                    event_id=event.event_id,
                    triggered=True,
                    reason="queued",
                    queued_request_id=request_id,
                )
            )
        return decisions


__all__ = ["WorkflowEngine"]
