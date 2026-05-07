"""Canonical reporting namespace.

Phase 1 compatibility export that gathers deterministic report/artifact renderers under
a package-first surface without moving implementations yet.
"""

from quant_stack.research.acceptance_artifacts import AcceptanceArtifactSet, Phase17ReportHelper, render_acceptance_report
from quant_stack.research.experiments.report import render_comparison_markdown
from quant_stack.research.reports import render_research_report
from quant_stack.reporting.backtest_report import (
    GateConfig,
    PipelineGateResult,
    ReportPolicy,
    run_pipeline_gate,
    write_backtest_artifacts,
)

__all__ = [
    "AcceptanceArtifactSet",
    "Phase17ReportHelper",
    "render_acceptance_report",
    "render_comparison_markdown",
    "render_research_report",
    "GateConfig",
    "PipelineGateResult",
    "ReportPolicy",
    "run_pipeline_gate",
    "write_backtest_artifacts",
]
