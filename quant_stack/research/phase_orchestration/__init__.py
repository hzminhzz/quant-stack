"""Phase 19 autonomous research pipeline orchestration."""

from quant_stack.research.phase_orchestration.gates import (
    gate_19b,
    gate_19c,
    gate_19d,
    gate_19e,
    gate_19f,
)
from quant_stack.research.phase_orchestration.phase_status import PhaseStatus
from quant_stack.research.phase_orchestration.phase19_runner import run_phase19_pipeline

__all__ = [
    "gate_19b",
    "gate_19c",
    "gate_19d",
    "gate_19e",
    "gate_19f",
    "PhaseStatus",
    "run_phase19_pipeline",
]