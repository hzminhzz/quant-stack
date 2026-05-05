"""Typed schemas for the Phase 12 optimization loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class RejectionReason(BaseModel):
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    severity: Literal["low", "medium", "high", "critical"] = "medium"


class AcceptanceCriteria(BaseModel):
    min_trades: int = Field(default=20, ge=0)
    min_oos_sharpe: float = 0.0
    max_drawdown: float = 0.16
    max_is_oos_sharpe_gap: float = 0.5
    min_walk_forward_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    max_turnover: float = Field(default=1.0, ge=0.0)
    min_profit_factor: float = 0.0
    max_daily_drawdown: float = 0.08
    require_positive_oos_return: bool = True


class OptimizationRequest(BaseModel):
    strategy_name: str = Field(..., min_length=1)
    symbols: list[str] = Field(..., min_length=1)
    timeframes: list[str] = Field(..., min_length=1)
    train_period: str = Field(..., min_length=1)
    test_period: str = Field(..., min_length=1)
    max_iterations: int = Field(default=3, ge=1, le=50)
    objective_name: str = Field(default="oos_robustness", min_length=1)
    acceptance_criteria: AcceptanceCriteria
    allowed_change_types: list[Literal["params", "features", "logic"]] = Field(default_factory=lambda: ["params"])
    created_by: str = "system"
    source_event_id: str | None = None
    context_filters: dict[str, Any] = Field(default_factory=dict)


class StrategyPatchProposal(BaseModel):
    strategy_name: str = Field(..., min_length=1)
    change_type: Literal["params", "features", "logic"]
    params: dict[str, Any] = Field(default_factory=dict)
    feature_changes: list[str] = Field(default_factory=list)
    logic_changes: list[str] = Field(default_factory=list)
    rationale: str = Field(..., min_length=5)
    expected_effect: str = Field(..., min_length=3)
    risks: list[str] = Field(default_factory=list)


class BacktestCritique(BaseModel):
    approved: bool
    summary: str = Field(..., min_length=1)
    failure_modes: list[str] = Field(default_factory=list)
    suspected_overfit: bool = False
    lookahead_risk: bool = False
    metric_weaknesses: list[str] = Field(default_factory=list)
    next_suggestions: list[str] = Field(default_factory=list)


class ObjectiveScore(BaseModel):
    score: float
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    metric_components: dict[str, float] = Field(default_factory=dict)
    penalties: dict[str, float] = Field(default_factory=dict)


class OptimizationCandidate(BaseModel):
    candidate_id: str
    proposal: StrategyPatchProposal
    status: Literal["proposed", "running", "completed", "rejected", "failed", "skipped"] = "proposed"
    result_path: str | None = None
    score: ObjectiveScore | None = None
    rejection_reason: RejectionReason | None = None


class OptimizationRun(BaseModel):
    run_id: str
    request: OptimizationRequest
    candidates: list[OptimizationCandidate] = Field(default_factory=list)
    best_candidate_id: str | None = None
    status: Literal["running", "approved", "rejected", "failed"] = "running"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class OptimizationResult(BaseModel):
    run_id: str
    best_candidate: OptimizationCandidate | None = None
    best_score: ObjectiveScore | None = None
    approved: bool = False
    summary: str = ""
    artifact_path: str


__all__ = [
    "AcceptanceCriteria",
    "BacktestCritique",
    "ObjectiveScore",
    "OptimizationCandidate",
    "OptimizationRequest",
    "OptimizationResult",
    "OptimizationRun",
    "RejectionReason",
    "StrategyPatchProposal",
]
