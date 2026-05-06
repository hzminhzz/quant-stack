"""Phase status models for Phase 19 autonomous pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PhaseState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineVerdict(str, Enum):
    ELIGIBLE = "eligible"
    ELIGIBLE_WITH_RISKS = "eligible_with_risks"
    NOT_ELIGIBLE = "not_eligible"
    PROMISING = "promising"
    MIXED = "mixed"
    WEAK = "weak"
    ROBUST = "robust"
    PROMISING_BUT_FRAGILE = "promising_but_fragile"
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"
    KEEP_BASELINE = "keep_baseline"
    STABLE_ALTERNATIVE_FOUND = "stable_alternative_found"
    FRAGILE_NEEDS_MORE_DATA = "fragile_needs_more_data"


@dataclass
class PhaseStatus:
    phase_id: str
    status: PhaseState = PhaseState.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    verdict: PipelineVerdict | None = None
    gate_passed: bool = False
    failure_reason: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "artifacts": self.artifacts,
            "verdict": self.verdict.value if self.verdict else None,
            "gate_passed": self.gate_passed,
            "failure_reason": self.failure_reason,
            "metrics": self.metrics,
        }


@dataclass
class DecisionLogEntry:
    phase: str
    timestamp: str
    gate_name: str
    inputs_checked: list[str]
    gate_result: str
    decision: str
    reason: str


@dataclass
class PipelineStatus:
    pipeline_id: str
    started_at: datetime
    completed_at: datetime | None = None
    current_phase: str | None = None
    completed_phases: list[str] = field(default_factory=list)
    failed_phase: str | None = None
    stop_reason: str | None = None
    symbols_processed: list[str] = field(default_factory=list)
    symbols_skipped: list[str] = field(default_factory=list)
    artifact_roots: dict[str, str] = field(default_factory=dict)
    final_verdict: PipelineVerdict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_phase": self.current_phase,
            "completed_phases": self.completed_phases,
            "failed_phase": self.failed_phase,
            "stop_reason": self.stop_reason,
            "symbols_processed": self.symbols_processed,
            "symbols_skipped": self.symbols_skipped,
            "artifact_roots": self.artifact_roots,
            "final_verdict": self.final_verdict.value if self.final_verdict else None,
        }


__all__ = [
    "PhaseState",
    "PipelineVerdict",
    "PhaseStatus",
    "DecisionLogEntry",
    "PipelineStatus",
]