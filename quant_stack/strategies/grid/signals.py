"""Grid strategy placeholder signal construction.

Grid execution is path-dependent, so this module intentionally exposes order
intent columns instead of pretending the strategy is a stateless signal stream.
"""

from __future__ import annotations

import polars as pl

from quant_stack.strategies.grid.params import GridParams


def build_features(df: pl.DataFrame, params: GridParams) -> pl.DataFrame:
    return df.sort("timestamp").with_columns(
        [
            pl.lit(params.num_levels).alias("grid_num_levels"),
            pl.lit(params.grid_width_pct).alias("grid_width_pct"),
            pl.lit(params.fee_pct).alias("grid_fee_pct"),
        ]
    )


def build_signals(df: pl.DataFrame, params: GridParams) -> pl.DataFrame:
    return build_features(df, params).with_columns(pl.lit(None).cast(pl.Int8).alias("signal"))


__all__ = ["build_features", "build_signals"]
