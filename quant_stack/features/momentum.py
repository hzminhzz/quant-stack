"""Momentum feature layer.

RSI here uses simple rolling-average gains/losses (not Wilder smoothing).
Warmup rows are null due to rolling min_samples.
Live parity with Wilder RSI is not guaranteed.
"""

from __future__ import annotations

import polars as pl


def rsi_expr(close_col: str = "close", window: int = 14, alias: str = "rsi_14") -> pl.Expr:
    delta = pl.col(close_col).diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0.0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0.0)
    avg_gain = gain.rolling_mean(window_size=window, min_samples=window)
    avg_loss = loss.rolling_mean(window_size=window, min_samples=window)
    value = (
        pl.when(avg_loss == 0)
        .then(pl.when(avg_gain == 0).then(50.0).otherwise(100.0))
        .otherwise(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))))
    )
    return value.alias(alias)


def momentum_expr(periods: int, alias: str) -> pl.Expr:
    return (pl.col("close") / pl.col("close").shift(periods) - 1.0).alias(alias)


def momentum_slope_expr(momentum_col: str, periods: int, alias: str) -> pl.Expr:
    return (pl.col(momentum_col) - pl.col(momentum_col).shift(periods)).alias(alias)


def price_extension_expr(window: int, alias: str) -> pl.Expr:
    base = pl.col("close").rolling_mean(window_size=window, min_samples=window)
    return ((pl.col("close") / base) - 1.0).alias(alias)


def add_momentum_features(df: pl.DataFrame, rsi_window: int) -> pl.DataFrame:
    out = df.with_columns(
        [
            rsi_expr(window=rsi_window, alias=f"rsi_{rsi_window}"),
            momentum_expr(10, "momentum_10"),
            momentum_expr(20, "momentum_20"),
            price_extension_expr(20, "price_extension_20"),
        ]
    )
    return out.with_columns(
        [
            momentum_slope_expr("momentum_10", 10, "momentum_slope_10"),
        ]
    )


__all__ = [
    "add_momentum_features",
    "momentum_expr",
    "momentum_slope_expr",
    "price_extension_expr",
    "rsi_expr",
]
