"""Deterministic signal scoring utilities."""

from __future__ import annotations

import polars as pl


def rolling_zscore(df: pl.DataFrame, *, value_col: str, window: int, out_col: str | None = None) -> pl.DataFrame:
    name = out_col or f"{value_col}_zscore"
    return df.with_columns(
        (
            (pl.col(value_col) - pl.col(value_col).rolling_mean(window_size=window, min_samples=window))
            / pl.col(value_col).rolling_std(window_size=window, min_samples=window)
        ).alias(name)
    )


def rolling_percentile(df: pl.DataFrame, *, value_col: str, window: int, out_col: str | None = None) -> pl.DataFrame:
    name = out_col or f"{value_col}_percentile"
    # rank over rolling window via map_elements on list window.
    return df.with_columns(
        pl.col(value_col)
        .rolling_map(
            function=lambda s: float((s <= s[-1]).sum() / len(s)) if len(s) else 0.0,
            window_size=window,
            min_samples=window,
        )
        .alias(name)
    )


def tag_extreme_events(
    df: pl.DataFrame,
    *,
    zscore_col: str,
    threshold: float = 2.0,
    out_col: str = "is_extreme",
) -> pl.DataFrame:
    return df.with_columns((pl.col(zscore_col).abs() >= threshold).fill_null(False).alias(out_col))


__all__ = ["rolling_percentile", "rolling_zscore", "tag_extreme_events"]
