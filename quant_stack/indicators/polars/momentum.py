"""Momentum indicators implemented as Polars expressions."""

from __future__ import annotations

import polars as pl


def rsi(column: str = "close", *, window: int = 14, alias: str | None = None) -> pl.Expr:
    """Rolling RSI using average gains and losses over `window` bars.

    This batch expression intentionally documents simple rolling RSI semantics.
    Live/Wilder-smoothed parity belongs in the later live-state phase.
    """

    if window <= 0:
        raise ValueError("window must be positive")
    delta = pl.col(column).diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0.0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0.0)
    avg_gain = gain.rolling_mean(window_size=window, min_samples=window)
    avg_loss = loss.rolling_mean(window_size=window, min_samples=window)
    value = pl.when(avg_loss == 0).then(100.0).otherwise(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))))
    return value.alias(alias or f"rsi_{window}")


__all__ = ["rsi"]
