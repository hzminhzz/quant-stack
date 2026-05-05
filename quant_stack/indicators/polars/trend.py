"""Trend indicators implemented as Polars expressions."""

from __future__ import annotations

import polars as pl


def sma(column: str = "close", *, window: int, alias: str | None = None) -> pl.Expr:
    """Simple moving average."""

    _validate_window(window)
    return pl.col(column).rolling_mean(window_size=window, min_samples=window).alias(alias or f"{column}_sma_{window}")


def ema(column: str = "close", *, span: int, alias: str | None = None) -> pl.Expr:
    """Exponential moving average."""

    _validate_window(span)
    return pl.col(column).ewm_mean(span=span, adjust=False, min_samples=span).alias(alias or f"{column}_ema_{span}")


def rolling_high(column: str = "high", *, window: int, alias: str | None = None) -> pl.Expr:
    """Rolling maximum."""

    _validate_window(window)
    return pl.col(column).rolling_max(window_size=window, min_samples=window).alias(alias or f"{column}_rolling_high_{window}")


def rolling_low(column: str = "low", *, window: int, alias: str | None = None) -> pl.Expr:
    """Rolling minimum."""

    _validate_window(window)
    return pl.col(column).rolling_min(window_size=window, min_samples=window).alias(alias or f"{column}_rolling_low_{window}")


def _validate_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")


__all__ = ["ema", "rolling_high", "rolling_low", "sma"]
