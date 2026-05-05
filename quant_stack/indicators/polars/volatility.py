"""Volatility indicators implemented as Polars expressions."""

from __future__ import annotations

import polars as pl


def rolling_volatility(column: str = "returns", *, window: int, alias: str | None = None) -> pl.Expr:
    """Rolling standard deviation of a return-like column."""

    _validate_window(window)
    return pl.col(column).rolling_std(window_size=window, min_samples=window).alias(alias or f"{column}_vol_{window}")


def rolling_zscore(column: str = "close", *, window: int, alias: str | None = None) -> pl.Expr:
    """Rolling z-score using population standard deviation."""

    _validate_window(window)
    mean = pl.col(column).rolling_mean(window_size=window, min_samples=window)
    std = pl.col(column).rolling_std(window_size=window, min_samples=window)
    return ((pl.col(column) - mean) / std).alias(alias or f"{column}_zscore_{window}")


def true_range(
    *,
    high: str = "high",
    low: str = "low",
    close: str = "close",
    alias: str = "true_range",
) -> pl.Expr:
    """True range expression."""

    previous_close = pl.col(close).shift(1)
    return pl.max_horizontal(
        pl.col(high) - pl.col(low),
        (pl.col(high) - previous_close).abs(),
        (pl.col(low) - previous_close).abs(),
    ).alias(alias)


def atr(
    *,
    high: str = "high",
    low: str = "low",
    close: str = "close",
    window: int = 14,
    alias: str | None = None,
) -> pl.Expr:
    """Average true range as a rolling mean of true range."""

    _validate_window(window)
    tr = true_range(high=high, low=low, close=close, alias="_true_range")
    return tr.rolling_mean(window_size=window, min_samples=window).alias(alias or f"atr_{window}")


def _validate_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")


__all__ = ["atr", "rolling_volatility", "rolling_zscore", "true_range"]
