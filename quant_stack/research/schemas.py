"""Typed schemas for the PydanticAI research layer."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RejectionReason(BaseModel):
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    severity: Literal["low", "medium", "high", "critical"] = "medium"


class StrategyIdea(BaseModel):
    name: str = Field(..., min_length=1)
    hypothesis: str = Field(..., min_length=10)
    asset_class: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    required_features: list[str] = Field(..., min_length=1)
    entry_logic: str = Field(..., min_length=5)
    exit_logic: str = Field(..., min_length=5)
    risk_logic: str = Field(..., min_length=5)
    expected_regime: str = Field(..., min_length=1)
    failure_modes: list[str] = Field(..., min_length=1)
    source_notes: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class FeatureIdea(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=5)
    required_columns: list[str] = Field(..., min_length=1)
    transformation_logic: str = Field(..., min_length=5)
    expected_predictive_mechanism: str = Field(..., min_length=5)
    leakage_risks: list[str] = Field(default_factory=list)


class CandidateParams(BaseModel):
    strategy_name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(..., min_length=1)
    constraints: list[str] = Field(default_factory=list)


class ExperimentPlan(BaseModel):
    strategy_name: str = Field(..., min_length=1)
    params_to_test: list[CandidateParams] = Field(..., min_length=1)
    symbols: list[str] = Field(..., min_length=1)
    timeframes: list[str] = Field(..., min_length=1)
    train_period: str = Field(..., min_length=1)
    test_period: str = Field(..., min_length=1)
    validation_method: str = Field(..., min_length=1)
    acceptance_criteria: list[str] = Field(..., min_length=1)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str]) -> list[str]:
        return [symbol.strip().upper() for symbol in symbols]

    @field_validator("timeframes")
    @classmethod
    def normalize_timeframes(cls, timeframes: list[str]) -> list[str]:
        return [timeframe.strip().lower() for timeframe in timeframes]


class ResearchCritique(BaseModel):
    lookahead_risk: str = Field(..., min_length=1)
    overfit_risk: str = Field(..., min_length=1)
    data_snooping_risk: str = Field(..., min_length=1)
    execution_risk: str = Field(..., min_length=1)
    market_regime_risk: str = Field(..., min_length=1)
    suggested_tests: list[str] = Field(default_factory=list)
    verdict: Literal["approve", "revise", "reject"]


class BacktestSummary(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    major_weaknesses: list[str] = Field(default_factory=list)
    pass_fail: Literal["pass", "fail"]
    artifact_path: str


class ValidationReport(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    artifact_path: str


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class ExperimentRecord(BaseModel):
    experiment_id: str
    strategy_name: str
    plan: ExperimentPlan
    created_by_agent: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    result_path: str | None = None
    rejection_reason: RejectionReason | None = None

    @model_validator(mode="after")
    def ensure_rejection_reason_when_rejected(self) -> "ExperimentRecord":
        if self.status == ExperimentStatus.REJECTED and self.rejection_reason is None:
            raise ValueError("rejected experiments require a rejection_reason")
        return self


__all__ = [
    "BacktestSummary",
    "CandidateParams",
    "ExperimentPlan",
    "ExperimentRecord",
    "ExperimentStatus",
    "FeatureIdea",
    "RejectionReason",
    "ResearchCritique",
    "StrategyIdea",
    "ValidationReport",
]
