"""Typed API contracts for backtest and optimization tool boundaries."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EngineName = Literal["auto", "polars"]
OutputMode = Literal["summary", "summary_with_top_trades", "full_artifact"]
RunStatus = Literal["ok", "rejected", "failed"]


class CostModelConfig(BaseModel):
    """Execution-cost assumptions for deterministic backtests."""

    fee_rate: float = 0.0
    slippage_bps: float = 0.0


class BacktestArtifact(BaseModel):
    """Persisted artifact references for a run.

    The API boundary returns file references instead of full tabular payloads.
    """

    run_id: str = Field(..., min_length=1)
    metrics_path: str = Field(..., min_length=1)
    summary_path: str = Field(..., min_length=1)
    equity_curve_path: str | None = None
    trades_path: str | None = None
    diagnostics_path: str | None = None
    config_path: str | None = None


class BacktestRequest(BaseModel):
    """Canonical backtest request contract for agent/tool callers."""

    strategy: str = Field(..., min_length=1)
    data_path: str = Field(..., min_length=1)
    symbol: str | None = None
    timeframe: str = "1m"
    params: dict[str, object] = Field(default_factory=dict)
    engine: EngineName = "auto"
    cost_model: CostModelConfig = CostModelConfig()
    output_mode: OutputMode = "summary"
    start: str | None = None
    end: str | None = None
    initial_capital: float = 10000.0


class BacktestSummary(BaseModel):
    """Agent-safe summary payload for one deterministic run."""

    run_id: str = Field(..., min_length=1)
    status: RunStatus = "ok"
    strategy: str = Field(..., min_length=1)
    symbol: str = Field("UNKNOWN", min_length=1)
    timeframe: str = "1m"
    rows: int = Field(0, ge=0)
    start: str | None = None
    end: str | None = None
    metrics: dict[str, float | int | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    artifact_refs: BacktestArtifact


class BatchBacktestRequest(BaseModel):
    """Batch backtest request contract for parameter sweeps."""

    strategy: str = Field(..., min_length=1)
    data_path: str = Field(..., min_length=1)
    param_matrix: list[dict[str, object]] = Field(..., min_length=1)
    symbol: str | None = None
    timeframe: str = Field("1m", min_length=1)
    engine: EngineName = "auto"
    cost_model: CostModelConfig = CostModelConfig()
    output_mode: OutputMode = "summary"
    top_n: int = Field(10, ge=1)


class BatchBacktestSummary(BaseModel):
    """Batch summary payload with top-N compressed results."""

    strategy: str = Field(..., min_length=1)
    total_candidates: int = Field(..., ge=1)
    completed_candidates: int = Field(..., ge=0)
    failed_candidates: int = Field(..., ge=0)
    top_results: list[BacktestSummary] = Field(default_factory=list)


__all__ = [
    "BacktestArtifact",
    "BacktestRequest",
    "BacktestSummary",
    "BatchBacktestRequest",
    "BatchBacktestSummary",
    "CostModelConfig",
]
