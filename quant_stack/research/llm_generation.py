"""LLM generation boundary models.

The research layer returns artifacts and candidate parameters. It does not
authorize execution or bypass deterministic validation.
"""

from __future__ import annotations

from quant_stack.artifacts.schemas import CandidateParams, ResearchArtifact, StrategyIdea
from quant_stack.research.guards import mark_generated_code_untrusted


def build_research_artifact(
    *,
    strategy_type: str,
    hypothesis: str,
    params: dict[str, object],
    paper_context: str = "",
    generated_code: str | None = None,
) -> ResearchArtifact:
    idea = StrategyIdea(strategy_type=strategy_type, hypothesis=hypothesis)
    candidate = CandidateParams(strategy_type=strategy_type, params=dict(params), rationale=hypothesis)
    return ResearchArtifact(
        idea=idea,
        candidate_params=candidate,
        paper_context=paper_context,
        generated_code=mark_generated_code_untrusted(generated_code) if generated_code else None,
        guard_passed=False if generated_code else None,
    )


__all__ = ["build_research_artifact"]
