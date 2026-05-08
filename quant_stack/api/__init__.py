"""Typed API layer for agent-safe quant_stack execution."""

from __future__ import annotations

from typing import Any

from .market_data import MarketFrameSchema, validate_market_frame
from .schemas import (
    BacktestArtifact,
    BacktestRequest,
    BacktestSummary,
    BatchBacktestRequest,
    BatchBacktestSummary,
    CostModelConfig,
    RunStatus,
)
from .tools import TOOLS


def to_backtest_summary(
    *,
    run_id: str,
    strategy: str,
    timeframe: str,
    rows: int,
    metrics: dict[str, Any],
    artifact_refs: BacktestArtifact,
    symbol: str = "UNKNOWN",
    status: RunStatus = "ok",
    start: str | None = None,
    end: str | None = None,
    warnings: list[str] | None = None,
) -> BacktestSummary:
    """Build an agent-safe backtest summary from internal result data."""

    normalized_metrics: dict[str, float | int | None] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            normalized_metrics[key] = int(value)
        elif isinstance(value, (int, float)) or value is None:
            normalized_metrics[key] = value
    return BacktestSummary(
        run_id=run_id,
        status=status,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        rows=rows,
        start=start,
        end=end,
        metrics=normalized_metrics,
        warnings=warnings or [],
        artifact_refs=artifact_refs,
    )

__all__ = [
    "BacktestArtifact",
    "BacktestRequest",
    "BacktestSummary",
    "BatchBacktestRequest",
    "BatchBacktestSummary",
    "CostModelConfig",
    "MarketFrameSchema",
    "to_backtest_summary",
    "validate_market_frame",
    "TOOLS",
]
