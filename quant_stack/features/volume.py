"""Volume and turnover feature engineering."""

from __future__ import annotations

import polars as pl


def rolling_zscore_expr(col: str, window: int, alias: str) -> pl.Expr:
    mean = pl.col(col).rolling_mean(window_size=window, min_samples=window)
    std = pl.col(col).rolling_std(window_size=window, min_samples=window)
    return ((pl.col(col) - mean) / std).alias(alias)


def add_volume_features(df: pl.DataFrame) -> pl.DataFrame:
    exprs = [
        rolling_zscore_expr("volume", 20, "volume_zscore_20"),
        rolling_zscore_expr("volume", 60, "volume_zscore_60"),
    ]
    if "turnover" in df.columns:
        exprs.append(rolling_zscore_expr("turnover", 20, "turnover_zscore_20"))
    out = df.with_columns(exprs)
    return out.with_columns((pl.col("volume_zscore_20") > 2.0).alias("volume_spike_20"))


__all__ = ["add_volume_features", "rolling_zscore_expr"]
