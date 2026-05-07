"""Canonical wrapper for the Phase 19 orchestration workflow."""

from __future__ import annotations

from pathlib import Path

from quant_stack.research.phase_orchestration import run_phase19_pipeline
from quant_stack.research.phase_orchestration.phase_status import PipelineStatus


def run_phase19(config_path: str | Path) -> PipelineStatus:
    return run_phase19_pipeline(Path(config_path))


__all__ = ["PipelineStatus", "run_phase19", "run_phase19_pipeline"]
