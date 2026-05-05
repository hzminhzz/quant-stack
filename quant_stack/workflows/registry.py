"""Workflow definition registry."""

from __future__ import annotations

from quant_stack.workflows.schemas import WorkflowDefinition


class WorkflowRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        if definition.workflow_id in self._definitions:
            raise ValueError(f"workflow already registered: {definition.workflow_id}")
        self._definitions[definition.workflow_id] = definition

    def list_enabled(self) -> list[WorkflowDefinition]:
        return [definition for definition in self._definitions.values() if definition.enabled]


__all__ = ["WorkflowRegistry"]
