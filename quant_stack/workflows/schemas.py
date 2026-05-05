"""Typed workflow schemas for event-driven optimization queueing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from quant_stack.research.optimization.schemas import AcceptanceCriteria, OptimizationRequest


class WorkflowEvent(BaseModel):
    event_id: str
    event_type: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context_tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    workflow_id: str
    enabled: bool = True
    strategy_name: str
    symbols: list[str] = Field(..., min_length=1)
    timeframes: list[str] = Field(..., min_length=1)
    required_context_tags: list[str] = Field(default_factory=list)
    cooldown_seconds: int = Field(default=0, ge=0)
    auto_approve: bool = False
    max_iterations_cap: int = Field(default=5, ge=1, le=50)
    allowed_change_types: list[Literal["params", "features", "logic"]] = Field(default_factory=lambda: ["params"])
    context_filters: dict[str, Any] = Field(default_factory=dict)
    acceptance_criteria: AcceptanceCriteria


class WorkflowDecision(BaseModel):
    workflow_id: str
    event_id: str
    triggered: bool
    reason: str
    queued_request_id: str | None = None


def workflow_request_from_definition(
    definition: WorkflowDefinition,
    *,
    event_id: str,
    train_period: str,
    test_period: str,
) -> OptimizationRequest:
    return OptimizationRequest(
        strategy_name=definition.strategy_name,
        symbols=definition.symbols,
        timeframes=definition.timeframes,
        train_period=train_period,
        test_period=test_period,
        max_iterations=min(definition.max_iterations_cap, 50),
        objective_name="oos_robustness",
        acceptance_criteria=definition.acceptance_criteria,
        allowed_change_types=definition.allowed_change_types or ["params"],
        created_by="workflow",
        source_event_id=event_id,
        context_filters=dict(definition.context_filters),
    )


__all__ = ["WorkflowDecision", "WorkflowDefinition", "WorkflowEvent", "workflow_request_from_definition"]
