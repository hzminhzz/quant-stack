"""Deterministic experiment queue for AI-proposed research plans."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from quant_stack.artifacts.store import load_artifact, save_artifact
from quant_stack.research.schemas import ExperimentPlan, ExperimentRecord, ExperimentStatus, RejectionReason


ALLOWED_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.PROPOSED: {ExperimentStatus.APPROVED, ExperimentStatus.REJECTED},
    ExperimentStatus.APPROVED: {ExperimentStatus.RUNNING, ExperimentStatus.REJECTED},
    ExperimentStatus.RUNNING: {ExperimentStatus.COMPLETED, ExperimentStatus.FAILED},
    ExperimentStatus.COMPLETED: set(),
    ExperimentStatus.REJECTED: set(),
    ExperimentStatus.FAILED: set(),
}


class ExperimentQueue:
    """JSON-backed queue for structured experiment requests."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: dict[str, ExperimentRecord] = {}
        self._optimization_records: dict[str, OptimizationRequestRecord] = {}
        if self.path.exists():
            snapshot = load_artifact(ExperimentQueueSnapshot, self.path)
            records = snapshot.records
            self._records = {record.experiment_id: record for record in records}
            self._optimization_records = {
                record.request_id: record for record in snapshot.optimization_requests
            }

    def submit(self, plan: ExperimentPlan, *, created_by_agent: str) -> ExperimentRecord:
        record = ExperimentRecord(
            experiment_id=f"exp-{uuid4().hex}",
            strategy_name=plan.strategy_name,
            plan=plan,
            created_by_agent=created_by_agent,
        )
        self._records[record.experiment_id] = record
        self.save()
        return record

    def get(self, experiment_id: str) -> ExperimentRecord:
        return self._records[experiment_id]

    def transition(
        self,
        experiment_id: str,
        status: ExperimentStatus,
        *,
        result_path: str | None = None,
        rejection_reason: RejectionReason | None = None,
    ) -> ExperimentRecord:
        current = self.get(experiment_id)
        if status not in ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(f"invalid experiment transition: {current.status.value} -> {status.value}")
        if status == ExperimentStatus.REJECTED and rejection_reason is None:
            raise ValueError("rejected transitions require a rejection_reason")
        updated = current.model_copy(update={"status": status, "result_path": result_path, "rejection_reason": rejection_reason})
        self._records[experiment_id] = updated
        self.save()
        return updated

    def list(self) -> list[ExperimentRecord]:
        return sorted(self._records.values(), key=lambda record: record.created_at)

    def submit_optimization_request(self, request: Any, *, auto_approve: bool = False) -> "OptimizationRequestRecord":
        normalized = _normalize_optimization_request(request)
        record = OptimizationRequestRecord(
            request_id=f"optreq-{uuid4().hex}",
            request_payload=normalized,
            created_by=str(normalized.get("created_by", "workflow")),
            status=OptimizationRequestStatus.PROPOSED,
        )
        self._optimization_records[record.request_id] = record
        if auto_approve:
            self._optimization_records[record.request_id] = record.model_copy(update={"status": OptimizationRequestStatus.APPROVED})
        self.save()
        return self._optimization_records[record.request_id]

    def transition_optimization_request(
        self,
        request_id: str,
        status: "OptimizationRequestStatus",
        *,
        result_path: str | None = None,
        rejection_reason: RejectionReason | None = None,
    ) -> "OptimizationRequestRecord":
        current = self._optimization_records[request_id]
        if status not in ALLOWED_OPTIMIZATION_TRANSITIONS[current.status]:
            raise ValueError(f"invalid optimization transition: {current.status.value} -> {status.value}")
        if status == OptimizationRequestStatus.REJECTED and rejection_reason is None:
            raise ValueError("rejected optimization requests require a rejection_reason")
        updated = current.model_copy(
            update={"status": status, "result_path": result_path, "rejection_reason": rejection_reason}
        )
        self._optimization_records[request_id] = updated
        self.save()
        return updated

    def list_optimization_requests(self, *, status: "OptimizationRequestStatus | None" = None) -> list["OptimizationRequestRecord"]:
        items = sorted(self._optimization_records.values(), key=lambda record: record.created_at)
        if status is None:
            return items
        return [item for item in items if item.status == status]

    def save(self) -> None:
        save_artifact(
            ExperimentQueueSnapshot(records=self.list(), optimization_requests=self.list_optimization_requests()),
            self.path,
        )


class ExperimentQueueSnapshot(BaseModel):
    records: list[ExperimentRecord] = Field(default_factory=list)
    optimization_requests: list["OptimizationRequestRecord"] = Field(default_factory=list)


class OptimizationRequestStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


ALLOWED_OPTIMIZATION_TRANSITIONS: dict[OptimizationRequestStatus, set[OptimizationRequestStatus]] = {
    OptimizationRequestStatus.PROPOSED: {OptimizationRequestStatus.APPROVED, OptimizationRequestStatus.REJECTED},
    OptimizationRequestStatus.APPROVED: {OptimizationRequestStatus.RUNNING, OptimizationRequestStatus.REJECTED},
    OptimizationRequestStatus.RUNNING: {OptimizationRequestStatus.COMPLETED, OptimizationRequestStatus.FAILED},
    OptimizationRequestStatus.COMPLETED: set(),
    OptimizationRequestStatus.REJECTED: set(),
    OptimizationRequestStatus.FAILED: set(),
}


class OptimizationRequestRecord(BaseModel):
    request_id: str
    request_payload: dict[str, Any]
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: OptimizationRequestStatus = OptimizationRequestStatus.PROPOSED
    result_path: str | None = None
    rejection_reason: RejectionReason | None = None

    @property
    def request(self) -> Any:
        return _normalize_optimization_request(self.request_payload, return_model=True)


def _normalize_optimization_request(request: Any, *, return_model: bool = False) -> Any:
    from quant_stack.research.optimization.schemas import OptimizationRequest

    model = request if isinstance(request, OptimizationRequest) else OptimizationRequest.model_validate(request)
    return model if return_model else model.model_dump()


__all__ = [
    "ALLOWED_OPTIMIZATION_TRANSITIONS",
    "ALLOWED_TRANSITIONS",
    "ExperimentQueue",
    "ExperimentQueueSnapshot",
    "OptimizationRequestRecord",
    "OptimizationRequestStatus",
]
