"""RSI/SMA feature and signal construction."""

from __future__ import annotations

import polars as pl

from quant_stack.indicators.polars.momentum import rsi
from quant_stack.indicators.polars.trend import sma
from quant_stack.strategies.rsi_sma.params import RSISMAParams


def build_features(df: pl.DataFrame, params: RSISMAParams) -> pl.DataFrame:
    return df.sort("timestamp").with_columns(
        [
            sma(window=params.short_sma, alias="short_sma"),
            sma(window=params.long_sma, alias="long_sma"),
            rsi(window=params.rsi_period, alias="rsi"),
        ]
    )


def build_signals(df: pl.DataFrame, params: RSISMAParams) -> pl.DataFrame:
    features = build_features(df, params)
    rsi_condition = pl.col("rsi") > params.rsi_threshold if params.rsi_side == "above" else pl.col("rsi") < params.rsi_threshold
    entry = (pl.col("short_sma").shift(1) <= pl.col("long_sma").shift(1)) & (pl.col("short_sma") > pl.col("long_sma")) & rsi_condition
    exit_signal = (pl.col("short_sma").shift(1) >= pl.col("long_sma").shift(1)) & (pl.col("short_sma") < pl.col("long_sma"))
    return features.with_columns(
        [
            entry.fill_null(False).alias("entry_signal"),
            exit_signal.fill_null(False).alias("exit_signal"),
        ]
    ).with_columns(
        pl.when(pl.col("entry_signal")).then(1).when(pl.col("exit_signal")).then(0).otherwise(None).alias("signal")
    )


__all__ = ["build_features", "build_signals"]
