"""Research guard helpers that keep generated code non-authoritative."""

from __future__ import annotations

from quant_stack.research.schemas import ExperimentPlan, RejectionReason, StrategyIdea


FORBIDDEN_RESEARCH_TERMS = (
    "future data",
    "future close",
    "next close",
    "shift(-",
    "lookahead",
    "broker",
    "live execution",
    "live trade",
    "place order",
    "risk limit",
    "bypass validation",
    "skip validation",
    "guaranteed profit",
    "will be profitable",
)

VAGUE_LOGIC_TERMS = ("some signal", "ai decides", "black box", "magic", "optimize later")


def mark_generated_code_untrusted(code: str) -> str:
    """Prefix generated code with an explicit non-production warning."""

    return "# GENERATED RESEARCH ARTIFACT - NOT PRODUCTION TRADING CODE\n" + code.lstrip()


def is_generated_code_marked(code: str) -> bool:
    return code.startswith("# GENERATED RESEARCH ARTIFACT - NOT PRODUCTION TRADING CODE")


def guard_strategy_idea(idea: StrategyIdea, *, available_features: set[str] | None = None) -> list[RejectionReason]:
    text = " ".join(
        [
            idea.hypothesis,
            idea.entry_logic,
            idea.exit_logic,
            idea.risk_logic,
            idea.expected_regime,
            " ".join(idea.failure_modes),
            " ".join(idea.source_notes),
        ]
    ).lower()
    reasons = _forbidden_text_reasons(text)
    if _is_vague(idea.entry_logic) or _is_vague(idea.exit_logic):
        reasons.append(RejectionReason(code="vague_logic", message="entry/exit logic is too vague", severity="high"))
    if _is_vague(idea.risk_logic):
        reasons.append(RejectionReason(code="missing_risk_logic", message="risk logic is missing or vague", severity="high"))
    if available_features is not None:
        missing = sorted(set(idea.required_features) - available_features)
        if missing:
            reasons.append(RejectionReason(code="unavailable_features", message=f"unavailable features: {', '.join(missing)}", severity="high"))
    return reasons


def guard_experiment_plan(
    plan: ExperimentPlan,
    *,
    registered_strategies: set[str],
    approved_symbols: set[str],
    approved_timeframes: set[str],
) -> list[RejectionReason]:
    reasons: list[RejectionReason] = []
    if plan.strategy_name not in registered_strategies:
        reasons.append(RejectionReason(code="unregistered_strategy", message=f"strategy is not registered: {plan.strategy_name}", severity="critical"))
    bad_symbols = sorted(set(plan.symbols) - approved_symbols)
    if bad_symbols:
        reasons.append(RejectionReason(code="unapproved_symbol", message=f"unapproved symbols: {', '.join(bad_symbols)}", severity="high"))
    bad_timeframes = sorted(set(plan.timeframes) - approved_timeframes)
    if bad_timeframes:
        reasons.append(RejectionReason(code="unapproved_timeframe", message=f"unapproved timeframes: {', '.join(bad_timeframes)}", severity="high"))
    text = " ".join([plan.validation_method, " ".join(plan.acceptance_criteria)]).lower()
    reasons.extend(_forbidden_text_reasons(text))
    return reasons


def _forbidden_text_reasons(text: str) -> list[RejectionReason]:
    return [
        RejectionReason(code="forbidden_research_claim", message=f"forbidden research term: {term}", severity="critical")
        for term in FORBIDDEN_RESEARCH_TERMS
        if term in text
    ]


def _is_vague(value: str) -> bool:
    lowered = value.strip().lower()
    return len(lowered) < 12 or any(term in lowered for term in VAGUE_LOGIC_TERMS)


__all__ = [
    "guard_experiment_plan",
    "guard_strategy_idea",
    "is_generated_code_marked",
    "mark_generated_code_untrusted",
]
