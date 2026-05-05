"""Research workflow helpers."""

from __future__ import annotations

from quant_stack.artifacts.schemas import CandidateParams


def candidate_params(strategy_type: str, params: dict[str, object], *, rationale: str = "") -> CandidateParams:
    return CandidateParams(strategy_type=strategy_type, params=dict(params), rationale=rationale)


__all__ = ["candidate_params"]
