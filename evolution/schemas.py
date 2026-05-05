from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BiasCheckReport(BaseModel):
    passed: bool
    summary: str = Field("")
    checks: dict[str, Any] = Field(default_factory=dict)


class ResearchGuardCheck(BaseModel):
    passed: bool
    detail: str = Field("")


class ResearchGuardReport(BaseModel):
    passed: bool
    summary: str = Field("")
    checks: dict[str, ResearchGuardCheck] = Field(default_factory=dict)


class EvolutionRun(BaseModel):
    run_id: str
    objective: str
    strategy_type: str
    status: Literal["planned", "running", "completed", "failed"] = Field("planned")
    created_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperienceEntry(BaseModel):
    experience_id: str
    run_id: str
    strategy_type: str
    candidate_name: str
    hypothesis: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    bias_check: BiasCheckReport | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class FailureEvent(BaseModel):
    event_id: str
    run_id: str
    experience_id: str | None = None
    stage: str
    failure_type: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
