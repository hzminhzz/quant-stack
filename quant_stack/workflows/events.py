"""Workflow event helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from quant_stack.intelligence.schemas import MarketContextSnapshot
from quant_stack.workflows.schemas import WorkflowEvent


def event_from_snapshot(
    snapshot: MarketContextSnapshot,
    *,
    event_type: str,
    timeframe: str,
    context_tags: list[str] | None = None,
) -> WorkflowEvent:
    return WorkflowEvent(
        event_id=f"evt-{uuid4().hex}",
        event_type=event_type,
        symbol=snapshot.symbol,
        timeframe=timeframe,
        timestamp=snapshot.timestamp if snapshot.timestamp.tzinfo is not None else snapshot.timestamp.replace(tzinfo=timezone.utc),
        context_tags=context_tags or [],
        payload={"snapshot": snapshot.model_dump()},
    )


def make_workflow_event(
    *,
    event_type: str,
    symbol: str,
    timeframe: str,
    context_tags: list[str] | None = None,
) -> WorkflowEvent:
    return WorkflowEvent(
        event_id=f"evt-{uuid4().hex}",
        event_type=event_type,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime.now(timezone.utc),
        context_tags=context_tags or [],
    )


__all__ = ["event_from_snapshot", "make_workflow_event"]
