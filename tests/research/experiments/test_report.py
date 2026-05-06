from __future__ import annotations

from quant_stack.research.experiments.report import render_comparison_markdown
from quant_stack.research.experiments.schemas import StrategyComparisonReport, StrategyExperimentResult


def test_report_renders_markdown() -> None:
    baseline = StrategyExperimentResult(strategy_name="x", mode="baseline", metrics={"total_return": 0.1})
    context = StrategyExperimentResult(strategy_name="x", mode="context", metrics={"total_return": 0.2})
    report = StrategyComparisonReport(
        strategy_name="x",
        baseline_result=baseline,
        context_result=context,
        metric_deltas={"total_return": 0.1},
        verdict="improved",
        warnings=[],
    )

    markdown = render_comparison_markdown(report)
    assert markdown.startswith("# Phase 18F Strategy Experiment")
    assert "## Metric Deltas" in markdown
