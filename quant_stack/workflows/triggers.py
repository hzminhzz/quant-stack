"""Workflow triggers."""

from __future__ import annotations

from dataclasses import dataclass

from quant_stack.workflows.schemas import WorkflowDefinition, WorkflowEvent


@dataclass(frozen=True)
class ContextTagTrigger:
    """Fire only when all required context tags are present."""

    def should_fire(self, definition: WorkflowDefinition, event: WorkflowEvent) -> bool:
        if not definition.required_context_tags:
            return True
        event_tags = set(event.context_tags)
        return all(tag in event_tags for tag in definition.required_context_tags)


__all__ = ["ContextTagTrigger"]
