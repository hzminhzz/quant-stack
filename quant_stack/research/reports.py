"""Deterministic report rendering helpers."""

from __future__ import annotations

from quant_stack.research.schemas import BacktestSummary, ResearchCritique, StrategyIdea, ValidationReport


def render_research_report(
    *,
    idea: StrategyIdea,
    backtest_summary: BacktestSummary,
    validation_report: ValidationReport,
    critique: ResearchCritique,
) -> str:
    status = "PASSED" if validation_report.passed else "FAILED"
    return "\n".join(
        [
            f"# Research Report: {idea.name}",
            "",
            f"**Status:** {status}",
            f"**Strategy:** {backtest_summary.strategy_name}",
            f"**Symbol/Timeframe:** {backtest_summary.symbol} / {backtest_summary.timeframe}",
            "",
            "## Hypothesis",
            idea.hypothesis,
            "",
            "## Critique Verdict",
            critique.verdict,
        ]
    )


__all__ = ["render_research_report"]
