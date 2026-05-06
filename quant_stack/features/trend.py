"""Trend feature expressions."""

from __future__ import annotations

import polars as pl


def ema_expr(col: str, span: int, alias: str) -> pl.Expr:
    return pl.col(col).ewm_mean(span=span, adjust=False, min_samples=span).alias(alias)


def ema_distance_expr(close_col: str, ema_col: str, alias: str) -> pl.Expr:
    return (pl.col(close_col) / pl.col(ema_col) - 1.0).alias(alias)


def add_trend_features(df: pl.DataFrame, ema_windows: list[int]) -> pl.DataFrame:
    out = df.with_columns([ema_expr("close", span, f"ema_{span}") for span in ema_windows])
    dist_exprs = [ema_distance_expr("close", f"ema_{span}", f"ema_dist_{span}") for span in ema_windows]
    out = out.with_columns(dist_exprs)
    return out.with_columns((pl.col("ema_50") / pl.col("ema_200") - 1.0).alias("trend_strength_50_200"))


__all__ = ["add_trend_features", "ema_distance_expr", "ema_expr"]
