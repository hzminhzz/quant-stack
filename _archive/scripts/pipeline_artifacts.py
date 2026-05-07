"""DEPRECATED compatibility artifact surface.

This root-level module remains for compatibility with older workflows. Canonical
artifact helpers should converge on `quant_stack.artifacts` and package-level
reporting surfaces over time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from evolution.schemas import EvolutionRun, ResearchGuardReport


DEFAULT_VALIDATION_ARTIFACT_PATH = Path("artifacts/latest_validation.json")
DEFAULT_SIGNAL_ARTIFACT_PATH = Path("artifacts/latest_signal.json")
DEFAULT_RESEARCH_ARTIFACT_PATH = Path("artifacts/latest_research.json")


class SignalArtifact(BaseModel):
    version: str = Field("1.0")
    strategy_type: str
    signal: dict[str, Any]
    source: str
    paper_context: str
    evolution_run: EvolutionRun | None = None


class ResearchArtifact(BaseModel):
    version: str = Field("1.0")
    strategy_type: str
    signal: dict[str, Any]
    paper_context: str
    polars_code: str
    guard_report: ResearchGuardReport | None = None
    evolution_run: EvolutionRun | None = None


class ValidationArtifact(BaseModel):
    version: str = Field("1.0")
    strategy_type: str
    params: dict[str, Any]
    rationale: str
    in_sample_metrics: dict[str, Any]
    in_sample_trade_count: int
    out_of_sample_metrics: dict[str, Any]
    out_of_sample_trade_count: int
    monte_carlo_95_dd_absolute_pct: float
    monte_carlo_median_dd_absolute_pct: float
    approved: bool
    critique: str
    evolution_run: EvolutionRun | None = None


def save_validation_artifact(artifact: ValidationArtifact, path: Path = DEFAULT_VALIDATION_ARTIFACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")


def save_signal_artifact(artifact: SignalArtifact, path: Path = DEFAULT_SIGNAL_ARTIFACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")


def save_research_artifact(artifact: ResearchArtifact, path: Path = DEFAULT_RESEARCH_ARTIFACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")


def load_validation_artifact(path: Path = DEFAULT_VALIDATION_ARTIFACT_PATH) -> ValidationArtifact:
    return ValidationArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def load_signal_artifact(path: Path = DEFAULT_SIGNAL_ARTIFACT_PATH) -> SignalArtifact:
    return SignalArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def load_research_artifact(path: Path = DEFAULT_RESEARCH_ARTIFACT_PATH) -> ResearchArtifact:
    return ResearchArtifact.model_validate_json(path.read_text(encoding="utf-8"))
