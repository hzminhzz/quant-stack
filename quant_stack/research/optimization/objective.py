"""Deterministic objective scoring for optimizer candidates."""

from __future__ import annotations

from typing import Any

from quant_stack.research.optimization.schemas import AcceptanceCriteria, ObjectiveScore
from quant_stack.research.schemas import BacktestSummary, ValidationReport


DEFAULT_WEIGHTS: dict[str, float] = {
    "oos_sharpe": 3.0,
    "profit_factor": 2.0,
    "walk_forward_pass_rate": 2.0,
    "max_drawdown": 3.0,
    "max_daily_drawdown": 2.0,
    "turnover": 1.0,
    "trade_count": 2.0,
    "is_oos_gap": 2.0,
    "oos_return": 2.0,
}


def score_objective(
    summary: BacktestSummary,
    validation: ValidationReport,
    criteria: AcceptanceCriteria,
    *,
    weights: dict[str, float] | None = None,
) -> ObjectiveScore:
    metrics = summary.metrics
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    oos_sharpe = _as_float(metrics.get("oos_sharpe", metrics.get("smart_sharpe", 0.0)))
    is_sharpe = _as_float(metrics.get("is_sharpe", oos_sharpe))
    max_drawdown = abs(_as_float(metrics.get("max_drawdown", 0.0)))
    max_daily_drawdown = abs(_as_float(metrics.get("max_daily_drawdown", 0.0)))
    turnover = _as_float(metrics.get("turnover", 0.0))
    trade_count = int(_as_float(metrics.get("trade_count", len(metrics.get("trades", [])))))
    profit_factor = _as_float(metrics.get("profit_factor", metrics.get("gain_pain_ratio", 0.0)))
    walk_forward_pass_rate = _as_float(metrics.get("walk_forward_pass_rate", 0.0))
    oos_return = _as_float(metrics.get("oos_return", metrics.get("cumulative_return", 0.0)))
    is_oos_gap = abs(is_sharpe - oos_sharpe)

    components = {
        "oos_sharpe_component": oos_sharpe * w["oos_sharpe"],
        "profit_factor_component": max(0.0, profit_factor) * w["profit_factor"],
        "walk_forward_component": walk_forward_pass_rate * w["walk_forward_pass_rate"],
    }
    penalties = {
        "max_drawdown_penalty": max(0.0, max_drawdown - criteria.max_drawdown) * w["max_drawdown"],
        "max_daily_drawdown_penalty": max(0.0, max_daily_drawdown - criteria.max_daily_drawdown) * w["max_daily_drawdown"],
        "turnover_penalty": max(0.0, turnover - criteria.max_turnover) * w["turnover"],
        "low_trade_count_penalty": max(0.0, criteria.min_trades - trade_count) * w["trade_count"],
        "overfit_gap_penalty": max(0.0, is_oos_gap - criteria.max_is_oos_sharpe_gap) * w["is_oos_gap"],
        "negative_oos_return_penalty": (w["oos_return"] if oos_return <= 0 else 0.0),
    }

    raw_score = sum(components.values()) - sum(penalties.values())

    failures: list[str] = []
    if trade_count < criteria.min_trades:
        failures.append("low_trade_count")
    if max_drawdown > criteria.max_drawdown:
        failures.append("max_drawdown_exceeded")
    if oos_sharpe < criteria.min_oos_sharpe:
        failures.append("oos_sharpe_below_minimum")
    if is_oos_gap > criteria.max_is_oos_sharpe_gap:
        failures.append("is_oos_sharpe_gap_too_large")
    if walk_forward_pass_rate < criteria.min_walk_forward_pass_rate:
        failures.append("walk_forward_pass_rate_too_low")
    if turnover > criteria.max_turnover:
        failures.append("turnover_too_high")
    if profit_factor < criteria.min_profit_factor:
        failures.append("profit_factor_too_low")
    if max_daily_drawdown > criteria.max_daily_drawdown:
        failures.append("max_daily_drawdown_exceeded")
    if criteria.require_positive_oos_return and oos_return <= 0:
        failures.append("oos_return_not_positive")
    if not validation.passed:
        failures.append("deterministic_validation_failed")

    return ObjectiveScore(
        score=float(raw_score),
        passed=not failures,
        failure_reasons=failures,
        metric_components={key: float(value) for key, value in components.items()},
        penalties={key: float(value) for key, value in penalties.items()},
    )


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["DEFAULT_WEIGHTS", "score_objective"]
