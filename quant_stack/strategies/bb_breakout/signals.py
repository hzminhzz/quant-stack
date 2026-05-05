"""Bollinger breakout feature and signal construction."""

from __future__ import annotations

import polars as pl

from quant_stack.indicators.polars.bands import bollinger_bands
from quant_stack.indicators.polars.trend import sma
from quant_stack.strategies.bb_breakout.params import BBBreakoutParams


def build_features(df: pl.DataFrame, params: BBBreakoutParams) -> pl.DataFrame:
    return df.sort("timestamp").with_columns(
        [
            *bollinger_bands(window=params.bb_length, num_std=params.bb_std),
            sma(window=params.regime_sma, alias="regime_sma"),
        ]
    )


def build_signals(df: pl.DataFrame, params: BBBreakoutParams) -> pl.DataFrame:
    features = build_features(df, params)
    entry = (pl.col("close") > pl.col("bb_upper")) & (pl.col("close") > pl.col("regime_sma"))
    exit_signal = pl.col("close") < pl.col("bb_middle")
    return features.with_columns(
        [
            entry.fill_null(False).alias("entry_signal"),
            exit_signal.fill_null(False).alias("exit_signal"),
        ]
    ).with_columns(
        pl.when(pl.col("entry_signal")).then(1).when(pl.col("exit_signal")).then(0).otherwise(None).alias("signal")
    )


__all__ = ["build_features", "build_signals"]
