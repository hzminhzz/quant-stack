"""Research discovery artifact helpers."""

from __future__ import annotations

from quant_stack.artifacts.schemas import StrategyIdea


def create_strategy_idea(strategy_type: str, hypothesis: str, *, source: str | None = None, evidence: list[str] | None = None) -> StrategyIdea:
    return StrategyIdea(strategy_type=strategy_type, hypothesis=hypothesis, source=source, evidence=evidence or [])


__all__ = ["create_strategy_idea"]
