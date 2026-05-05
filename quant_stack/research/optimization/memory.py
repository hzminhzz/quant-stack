"""Optimization memory store for candidate history and failure modes."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from quant_stack.artifacts.store import load_artifact, save_artifact
from quant_stack.research.optimization.guards import params_fingerprint
from quant_stack.research.optimization.schemas import OptimizationCandidate


class OptimizationMemorySnapshot(BaseModel):
    run_id: str
    candidates: list[OptimizationCandidate] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    accepted_candidate_ids: list[str] = Field(default_factory=list)


class OptimizationMemory:
    def __init__(self, path: str | Path, *, run_id: str) -> None:
        self.path = Path(path)
        if self.path.exists():
            self.snapshot = load_artifact(OptimizationMemorySnapshot, self.path)
        else:
            self.snapshot = OptimizationMemorySnapshot(run_id=run_id)

    def add_candidate(self, candidate: OptimizationCandidate) -> None:
        self.snapshot.candidates.append(candidate)
        if candidate.rejection_reason is not None:
            self.snapshot.failure_modes.append(candidate.rejection_reason.code)
        if candidate.status == "completed" and candidate.score is not None and candidate.score.passed:
            self.snapshot.accepted_candidate_ids.append(candidate.candidate_id)
        self.save()

    def tested_param_fingerprints(self) -> set[str]:
        fingerprints: set[str] = set()
        for candidate in self.snapshot.candidates:
            if candidate.proposal.params:
                fingerprints.add(params_fingerprint(candidate.proposal.params))
        return fingerprints

    def save(self) -> None:
        save_artifact(self.snapshot, self.path)


__all__ = ["OptimizationMemory", "OptimizationMemorySnapshot"]
