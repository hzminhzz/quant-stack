"""Polars metrics for backtest result frames."""

from __future__ import annotations

from math import sqrt
from typing import Any

import numpy as np
import polars as pl


def calculate_metrics(df: pl.DataFrame, *, initial_capital: float = 1.0) -> dict[str, Any]:
    """Calculate core validation metrics from `timestamp`, `equity`, `is_exposed`."""

    if df.is_empty():
        return _empty_metrics()
    _require_columns(df, ["timestamp", "equity", "is_exposed"])
    frame = df.sort("timestamp")
    last_equity = float(frame.select(pl.col("equity").last()).item())
    cumulative_return = (last_equity / initial_capital) - 1.0
    start_date = frame.select(pl.col("timestamp").min()).item()
    end_date = frame.select(pl.col("timestamp").max()).item()
    days_elapsed = (end_date - start_date).total_seconds() / 86400.0 if start_date != end_date else 0.0
    cagr = _safe_cagr(last_equity, initial_capital, days_elapsed)
    frame = frame.with_columns(pl.col("equity").cum_max().alias("peak_equity"))
    max_drawdown = float(frame.select(((pl.col("equity") - pl.col("peak_equity")) / pl.col("peak_equity")).min()).item() or 0.0)
    time_in_market = float(frame.select(pl.col("is_exposed").mean()).item() or 0.0)
    daily = _daily_returns(frame)
    return {
        "cumulative_return": cumulative_return,
        "cagr": cagr,
        "time_in_market": time_in_market,
        "max_drawdown": max_drawdown,
        "max_daily_drawdown": _max_daily_drawdown(daily),
        "max_consecutive_losing_days": _max_consecutive_losing_days(daily),
        "smart_sharpe": _sharpe(daily),
        "smart_sortino": _sortino(daily),
        "tail_ratio": _tail_ratio(daily),
        "gain_pain_ratio": _gain_pain_ratio(daily),
        "kelly_criterion": _kelly(daily),
    }


def _daily_returns(frame: pl.DataFrame) -> pl.DataFrame:
    daily = frame.group_by(pl.col("timestamp").dt.date().alias("date")).agg(
        [
            pl.col("equity").first().alias("open_eq"),
            pl.col("equity").min().alias("min_eq"),
            pl.col("equity").last().alias("close_eq"),
        ]
    ).sort("date")
    return daily.with_columns(
        [
            ((pl.col("min_eq") - pl.col("open_eq")) / pl.col("open_eq")).alias("daily_dd"),
            ((pl.col("close_eq") - pl.col("open_eq")) / pl.col("open_eq")).alias("daily_return"),
        ]
    )


def _safe_cagr(last_equity: float, initial_capital: float, days_elapsed: float) -> float:
    if days_elapsed <= 0 or last_equity <= 0:
        return 0.0
    try:
        return float((last_equity / initial_capital) ** (365.0 / days_elapsed) - 1.0)
    except OverflowError:
        return float("inf")


def _max_daily_drawdown(daily: pl.DataFrame) -> float:
    return float(daily.select(pl.col("daily_dd").min()).item() or 0.0)


def _max_consecutive_losing_days(daily: pl.DataFrame) -> int:
    if daily.is_empty():
        return 0
    streaks = daily.with_columns((pl.col("daily_return") < 0).cast(pl.Int32).alias("is_loss")).with_columns(
        (pl.col("is_loss") != pl.col("is_loss").shift(1)).fill_null(True).cum_sum().alias("streak_id")
    )
    losses = streaks.filter(pl.col("is_loss") == 1).group_by("streak_id").agg(pl.len().alias("streak_len"))
    return int(losses.select(pl.col("streak_len").max()).item() or 0) if not losses.is_empty() else 0


def _returns_array(daily: pl.DataFrame) -> np.ndarray:
    return daily.select("daily_return").drop_nulls().to_numpy().ravel().astype(float)


def _sharpe(daily: pl.DataFrame) -> float:
    returns = _returns_array(daily)
    if len(returns) < 2 or np.std(returns, ddof=1) == 0:
        return 0.0
    return float(np.mean(returns) / np.std(returns, ddof=1) * sqrt(365.0))


def _sortino(daily: pl.DataFrame) -> float:
    returns = _returns_array(daily)
    downside = returns[returns < 0]
    if len(downside) < 2 or np.std(downside, ddof=1) == 0:
        return 0.0
    return float(np.mean(returns) / np.std(downside, ddof=1) * sqrt(365.0))


def _tail_ratio(daily: pl.DataFrame) -> float:
    returns = _returns_array(daily)
    if len(returns) == 0:
        return 0.0
    p5 = float(np.quantile(returns, 0.05))
    return float(abs(np.quantile(returns, 0.95) / p5)) if p5 != 0 else float("inf")


def _gain_pain_ratio(daily: pl.DataFrame) -> float:
    returns = _returns_array(daily)
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    return float(gains / losses) if losses > 0 else float("inf") if gains > 0 else 0.0


def _kelly(daily: pl.DataFrame) -> float:
    returns = _returns_array(daily)
    if len(returns) == 0:
        return 0.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    if len(wins) == 0:
        return 0.0
    if len(losses) == 0:
        return 1.0
    win_rate = len(wins) / len(returns)
    ratio = float(np.mean(wins) / abs(np.mean(losses)))
    return float(win_rate - ((1.0 - win_rate) / ratio)) if ratio > 0 else 0.0


def _empty_metrics() -> dict[str, Any]:
    return {
        "cumulative_return": 0.0,
        "cagr": 0.0,
        "time_in_market": 0.0,
        "max_drawdown": 0.0,
        "max_daily_drawdown": 0.0,
        "max_consecutive_losing_days": 0,
        "smart_sharpe": 0.0,
        "smart_sortino": 0.0,
        "tail_ratio": 0.0,
        "gain_pain_ratio": 0.0,
        "kelly_criterion": 0.0,
    }


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"missing required metrics column(s): {', '.join(missing)}")


__all__ = ["calculate_metrics"]
