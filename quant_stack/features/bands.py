"""Bollinger-band-derived features."""

from __future__ import annotations

import polars as pl


def bollinger_exprs(close_col: str, window: int, n_std: float) -> list[pl.Expr]:
    mid = pl.col(close_col).rolling_mean(window_size=window, min_samples=window)
    std = pl.col(close_col).rolling_std(window_size=window, min_samples=window, ddof=0)
    upper = mid + (n_std * std)
    lower = mid - (n_std * std)
    return [
        mid.alias(f"bb_mid_{window}"),
        upper.alias(f"bb_upper_{window}"),
        lower.alias(f"bb_lower_{window}"),
        ((upper - lower) / mid).alias(f"bb_width_{window}"),
        ((pl.col(close_col) - lower) / (upper - lower)).alias(f"bb_pos_{window}"),
    ]


def add_bollinger_features(df: pl.DataFrame, window: int, n_std: float) -> pl.DataFrame:
    out = df.with_columns(bollinger_exprs("close", window, n_std))
    lower_col = f"bb_lower_{window}"
    upper_col = f"bb_upper_{window}"
    return out.with_columns(
        [
            ((pl.col("close").shift(1) < pl.col(lower_col).shift(1)) & (pl.col("close") > pl.col(lower_col))).alias(
                "bb_reclaim_lower"
            ),
            ((pl.col("close").shift(1) > pl.col(upper_col).shift(1)) & (pl.col("close") < pl.col(upper_col))).alias(
                "bb_reclaim_upper"
            ),
            ((pl.col("close").shift(1) < pl.col(lower_col).shift(1)) & (pl.col("close") > pl.col(lower_col).shift(1))).alias(
                "bb_reclaim_lower_strict"
            ),
            ((pl.col("close").shift(1) > pl.col(upper_col).shift(1)) & (pl.col("close") < pl.col(upper_col).shift(1))).alias(
                "bb_reclaim_upper_strict"
            ),
        ]
    )


__all__ = ["add_bollinger_features", "bollinger_exprs"]
