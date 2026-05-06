"""Volatility feature expressions and DataFrame transforms."""

from __future__ import annotations

import polars as pl


def rolling_vol_expr(return_col: str, window: int, alias: str) -> pl.Expr:
    return pl.col(return_col).rolling_std(window_size=window, min_samples=window).alias(alias)


def range_pct_expr() -> pl.Expr:
    return ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("range_pct")


def true_range_expr() -> pl.Expr:
    previous_close = pl.col("close").shift(1)
    return pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - previous_close).abs(),
        (pl.col("low") - previous_close).abs(),
    ).alias("true_range")


def atr_expr(window: int, alias: str) -> pl.Expr:
    return pl.col("true_range").rolling_mean(window_size=window, min_samples=window).alias(alias)


def add_volatility_features(df: pl.DataFrame, windows: list[int], atr_window: int) -> pl.DataFrame:
    out = df.with_columns([range_pct_expr(), true_range_expr()])
    out = out.with_columns([atr_expr(atr_window, f"atr_{atr_window}")])
    exprs: list[pl.Expr] = [(pl.col(f"atr_{atr_window}") / pl.col("close")).alias(f"atr_pct_{atr_window}")]
    for window in windows:
        exprs.append(rolling_vol_expr("ret_1", window, f"realized_vol_{window}"))
    return out.with_columns(exprs)


__all__ = ["add_volatility_features", "atr_expr", "range_pct_expr", "rolling_vol_expr", "true_range_expr"]
