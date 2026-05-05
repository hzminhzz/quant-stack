"""Guardrails for optimizer proposals."""

from __future__ import annotations

import json

from quant_stack.research.optimization.schemas import RejectionReason, StrategyPatchProposal


FORBIDDEN_TERMS = (
    "future data",
    "shift(-",
    "lookahead",
    "broker",
    "ccxt",
    "live execution",
    "place order",
    "risk limit",
    "disable risk",
    "skip validation",
    "pandas",
    "strategy_families",
    "deploy directly",
    "production deploy",
    "fill assumption",
    "close_to_close ->",
)

VAGUE_TERMS = ("ai decides", "magic", "optimize later", "some logic")


def guard_patch_proposal(
    proposal: StrategyPatchProposal,
    *,
    allowed_change_types: set[str],
    tested_param_fingerprints: set[str] | None = None,
) -> list[RejectionReason]:
    reasons: list[RejectionReason] = []
    if proposal.change_type not in allowed_change_types:
        reasons.append(RejectionReason(code="change_type_not_allowed", message=f"change_type not allowed: {proposal.change_type}", severity="high"))

    text = " ".join(
        [
            proposal.rationale,
            proposal.expected_effect,
            " ".join(proposal.feature_changes),
            " ".join(proposal.logic_changes),
            " ".join(proposal.risks),
        ]
    ).lower()

    for term in FORBIDDEN_TERMS:
        if term in text:
            reasons.append(RejectionReason(code="forbidden_proposal_term", message=f"forbidden term: {term}", severity="critical"))
    if any(term in text for term in VAGUE_TERMS) or len(proposal.rationale.strip()) < 8:
        reasons.append(RejectionReason(code="vague_logic", message="proposal rationale/logic is too vague", severity="high"))

    if tested_param_fingerprints is not None and proposal.params:
        fingerprint = params_fingerprint(proposal.params)
        if fingerprint in tested_param_fingerprints:
            reasons.append(RejectionReason(code="duplicate_params", message="proposal duplicates already-tested params", severity="medium"))

    return reasons


def params_fingerprint(params: dict[str, object]) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


__all__ = ["guard_patch_proposal", "params_fingerprint"]
