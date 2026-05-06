from __future__ import annotations

from quant_stack.research.experiments.comparison import compare_results
from quant_stack.research.experiments.schemas import StrategyExperimentResult


def test_comparison_computes_metric_deltas() -> None:
    baseline = StrategyExperimentResult(
        strategy_name="forced_flow_band_reclaim",
        mode="baseline",
        metrics={
            "total_return": 0.10,
            "sharpe": 1.0,
            "max_drawdown": -0.20,
            "trade_count": 10,
            "exposure": 0.7,
            "win_rate": 0.4,
            "profit_factor": 1.1,
        },
    )
    context = StrategyExperimentResult(
        strategy_name="forced_flow_band_reclaim",
        mode="context",
        metrics={
            "total_return": 0.15,
            "sharpe": 1.3,
            "max_drawdown": -0.10,
            "trade_count": 8,
            "exposure": 0.5,
            "win_rate": 0.5,
            "profit_factor": 1.4,
        },
    )

    report = compare_results(
        strategy_name="forced_flow_band_reclaim",
        baseline_result=baseline,
        context_result=context,
    )
    assert report.metric_deltas["total_return"] > 0
    assert report.metric_deltas["max_drawdown"] > 0
    assert report.verdict in {"improved", "promising", "inconclusive", "reject"}
