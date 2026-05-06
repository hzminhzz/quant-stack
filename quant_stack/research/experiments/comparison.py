"""Comparison logic for baseline vs context experiment results."""

from __future__ import annotations

from quant_stack.research.experiments.schemas import StrategyComparisonReport, StrategyExperimentResult


def compare_results(
    *,
    strategy_name: str,
    baseline_result: StrategyExperimentResult,
    context_result: StrategyExperimentResult,
) -> StrategyComparisonReport:
    metric_deltas = {
        "total_return": _metric_value(context_result, "total_return") - _metric_value(baseline_result, "total_return"),
        "sharpe": _metric_value(context_result, "sharpe") - _metric_value(baseline_result, "sharpe"),
        "max_drawdown": _metric_value(context_result, "max_drawdown") - _metric_value(baseline_result, "max_drawdown"),
        "trade_count": _metric_value(context_result, "trade_count") - _metric_value(baseline_result, "trade_count"),
        "exposure": _metric_value(context_result, "exposure") - _metric_value(baseline_result, "exposure"),
        "win_rate": _metric_value(context_result, "win_rate") - _metric_value(baseline_result, "win_rate"),
        "profit_factor": _metric_value(context_result, "profit_factor") - _metric_value(baseline_result, "profit_factor"),
    }
    verdict = _verdict(baseline_result, context_result)
    warnings = _warnings(baseline_result, context_result)
    return StrategyComparisonReport(
        strategy_name=strategy_name,
        baseline_result=baseline_result,
        context_result=context_result,
        metric_deltas=metric_deltas,
        verdict=verdict,
        warnings=warnings,
    )


def _metric_value(result: StrategyExperimentResult, key: str) -> float:
    value = result.metrics.get(key, 0.0)
    return float(value) if value is not None else 0.0


def _verdict(baseline: StrategyExperimentResult, context: StrategyExperimentResult) -> str:
    base_return = _metric_value(baseline, "total_return")
    ctx_return = _metric_value(context, "total_return")
    base_dd = abs(_metric_value(baseline, "max_drawdown"))
    ctx_dd = abs(_metric_value(context, "max_drawdown"))
    base_sharpe = _metric_value(baseline, "sharpe")
    ctx_sharpe = _metric_value(context, "sharpe")
    base_trades = _metric_value(baseline, "trade_count")
    ctx_trades = _metric_value(context, "trade_count")
    base_exposure = _metric_value(baseline, "exposure")
    ctx_exposure = _metric_value(context, "exposure")
    base_quality = _metric_value(baseline, "win_rate") + _metric_value(baseline, "profit_factor")
    ctx_quality = _metric_value(context, "win_rate") + _metric_value(context, "profit_factor")

    if ctx_return > base_return and ctx_dd < base_dd:
        return "improved"
    if ctx_trades < base_trades and ctx_sharpe > base_sharpe:
        return "promising"
    if ctx_exposure < base_exposure and ctx_quality <= base_quality:
        return "inconclusive"
    if ctx_return < base_return and ctx_sharpe <= base_sharpe:
        return "reject"
    return "inconclusive"


def _warnings(baseline: StrategyExperimentResult, context: StrategyExperimentResult) -> list[str]:
    warnings: list[str] = []
    if _metric_value(context, "trade_count") == 0:
        warnings.append("context mode produced zero closed trades")
    if _metric_value(baseline, "trade_count") == 0:
        warnings.append("baseline mode produced zero closed trades")
    if _metric_value(context, "exposure") < 0.01:
        warnings.append("context mode exposure is near zero")
    if _metric_value(context, "total_return") == _metric_value(baseline, "total_return"):
        warnings.append("total_return identical between baseline and context")
    return warnings


__all__ = ["compare_results"]
