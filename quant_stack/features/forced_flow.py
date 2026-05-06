"""Forced-flow proxy features (heuristics, not true liquidation labels)."""

from __future__ import annotations

import polars as pl

from quant_stack.features.schemas import FeatureThresholdConfig


def add_forced_flow_proxy_features(df: pl.DataFrame, thresholds: FeatureThresholdConfig) -> pl.DataFrame:
    out = df
    if "return_zscore_60" not in out.columns:
        mean = pl.col("ret_1").rolling_mean(window_size=60, min_samples=60)
        std = pl.col("ret_1").rolling_std(window_size=60, min_samples=60)
        out = out.with_columns(((pl.col("ret_1") - mean) / std).alias("return_zscore_60"))

    if "oi_flush" not in out.columns:
        out = out.with_columns(pl.lit(False).alias("oi_flush"))

    out = out.with_columns(
        [
            (pl.col("return_zscore_60") < -thresholds.return_zscore_shock).alias("return_shock_down"),
            (pl.col("return_zscore_60") > thresholds.return_zscore_shock).alias("return_shock_up"),
            (pl.col("volume_zscore_20") > thresholds.volume_zscore_spike).alias("volume_shock"),
            pl.col("oi_flush").fill_null(False).alias("oi_flush_event"),
        ]
    )

    out = out.with_columns(
        [
            (pl.col("return_shock_down") & pl.col("volume_shock") & pl.col("oi_flush_event")).alias("forced_selling_proxy"),
            (pl.col("return_shock_up") & pl.col("volume_shock") & pl.col("oi_flush_event")).alias("forced_buying_proxy"),
        ]
    )
    return out.with_columns(
        [
            (pl.col("forced_selling_proxy") & pl.col("bb_reclaim_lower").fill_null(False)).alias("liquidation_proxy_long"),
            (pl.col("forced_buying_proxy") & pl.col("bb_reclaim_upper").fill_null(False)).alias("liquidation_proxy_short"),
        ]
    )


__all__ = ["add_forced_flow_proxy_features"]
