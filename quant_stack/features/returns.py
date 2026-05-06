"""Return features for canonical market datasets."""

from __future__ import annotations

import polars as pl


def pct_return_expr(col: str, periods: int, alias: str) -> pl.Expr:
    return pl.col(col).pct_change(periods).alias(alias)


def log_return_expr(col: str, periods: int, alias: str) -> pl.Expr:
    return (pl.col(col) / pl.col(col).shift(periods)).log().alias(alias)


def abs_return_expr(col: str, periods: int, alias: str) -> pl.Expr:
    return pl.col(col).pct_change(periods).abs().alias(alias)


def add_return_features(df: pl.DataFrame, windows: list[int]) -> pl.DataFrame:
    exprs: list[pl.Expr] = []
    for window in windows:
        exprs.append(pct_return_expr("close", window, f"ret_{window}"))
        if window in {1, 5}:
            exprs.append(log_return_expr("close", window, f"log_ret_{window}"))
    exprs.append(abs_return_expr("close", 1, "abs_ret_1"))
    return df.with_columns(exprs)


__all__ = ["abs_return_expr", "add_return_features", "log_return_expr", "pct_return_expr"]
