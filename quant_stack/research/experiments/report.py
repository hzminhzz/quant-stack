"""Markdown rendering for Phase 18F experiment reports."""

from __future__ import annotations

import json

from quant_stack.research.experiments.schemas import StrategyComparisonReport


def render_comparison_markdown(report: StrategyComparisonReport) -> str:
    return "\n".join(
        [
            f"# Phase 18F Strategy Experiment: {report.strategy_name}",
            "",
            f"**Verdict:** {report.verdict}",
            "",
            "## Baseline Metrics",
            f"```json\n{json.dumps(report.baseline_result.metrics, indent=2, sort_keys=True)}\n```",
            "",
            "## Context Metrics",
            f"```json\n{json.dumps(report.context_result.metrics, indent=2, sort_keys=True)}\n```",
            "",
            "## Metric Deltas (Context - Baseline)",
            f"```json\n{json.dumps(report.metric_deltas, indent=2, sort_keys=True)}\n```",
            "",
            "## Warnings",
            *([f"- {warning}" for warning in report.warnings] if report.warnings else ["- none"]),
            "",
        ]
    )


__all__ = ["render_comparison_markdown"]
