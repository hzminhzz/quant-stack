"""Regime tagging from base and derivatives features."""

from __future__ import annotations

import polars as pl

from quant_stack.features.schemas import FeatureThresholdConfig, FeatureWindowConfig


def add_trend_regime(df: pl.DataFrame, threshold: float = 0.0) -> pl.DataFrame:
    return df.with_columns(
        pl.when(pl.col("trend_strength_50_200") > threshold)
        .then(pl.lit("up"))
        .when(pl.col("trend_strength_50_200") < -threshold)
        .then(pl.lit("down"))
        .otherwise(pl.lit("range"))
        .alias("trend_regime")
    )


def add_volatility_regime(df: pl.DataFrame) -> pl.DataFrame:
    high = pl.col("realized_vol_60").rolling_quantile(0.75, window_size=240, min_samples=120)
    low = pl.col("realized_vol_60").rolling_quantile(0.25, window_size=240, min_samples=120)
    return df.with_columns(
        pl.when(pl.col("realized_vol_60") > high)
        .then(pl.lit("high_vol"))
        .when(pl.col("realized_vol_60") < low)
        .then(pl.lit("low_vol"))
        .otherwise(pl.lit("normal_vol"))
        .alias("volatility_regime")
    )


def add_funding_regime(df: pl.DataFrame, allow_missing: bool = True) -> pl.DataFrame:
    if "funding_positive_extreme" not in df.columns or "funding_negative_extreme" not in df.columns:
        if allow_missing:
            return df.with_columns(pl.lit("missing").alias("funding_regime"))
        raise ValueError("funding extreme columns missing")
    return df.with_columns(
        pl.when(pl.col("funding_positive_extreme")).then(pl.lit("positive_extreme"))
        .when(pl.col("funding_negative_extreme")).then(pl.lit("negative_extreme"))
        .otherwise(pl.lit("neutral"))
        .alias("funding_regime")
    )


def add_oi_regime(df: pl.DataFrame, allow_missing: bool = True) -> pl.DataFrame:
    if "oi_expansion" not in df.columns:
        if allow_missing:
            return df.with_columns(pl.lit("missing").alias("oi_regime"))
        raise ValueError("oi_expansion missing")
    return df.with_columns(
        pl.when(pl.col("oi_expansion")).then(pl.lit("expansion"))
        .when(pl.col("oi_flush")).then(pl.lit("flush"))
        .otherwise(pl.lit("neutral"))
        .alias("oi_regime")
    )


def add_basis_regime(df: pl.DataFrame, allow_missing: bool = True) -> pl.DataFrame:
    if "perp_premium_extreme" not in df.columns:
        if allow_missing:
            return df.with_columns(pl.lit("missing").alias("basis_regime"))
        raise ValueError("basis features missing")
    return df.with_columns(
        pl.when(pl.col("perp_premium_extreme")).then(pl.lit("premium_extreme"))
        .when(pl.col("perp_discount_extreme")).then(pl.lit("discount_extreme"))
        .otherwise(pl.lit("neutral"))
        .alias("basis_regime")
    )


def add_regime_features(
    df: pl.DataFrame,
    config: FeatureWindowConfig,
    thresholds: FeatureThresholdConfig,
    *,
    allow_missing: bool,
) -> pl.DataFrame:
    out = add_trend_regime(df, thresholds.trend_threshold)
    out = add_volatility_regime(out)
    out = add_funding_regime(out, allow_missing=allow_missing)
    out = add_oi_regime(out, allow_missing=allow_missing)
    out = add_basis_regime(out, allow_missing=allow_missing)
    return out.with_columns(
        [
            (pl.col("trend_regime") == "up").alias("tag_trend_up"),
            (pl.col("trend_regime") == "down").alias("tag_trend_down"),
            (pl.col("volatility_regime") == "high_vol").alias("tag_high_vol"),
            (pl.col("volatility_regime") == "low_vol").alias("tag_low_vol"),
            (pl.col("funding_regime") == "positive_extreme").alias("tag_positive_funding_extreme"),
            (pl.col("funding_regime") == "negative_extreme").alias("tag_negative_funding_extreme"),
            (pl.col("oi_regime") == "expansion").alias("tag_oi_expansion"),
            (pl.col("oi_regime") == "flush").alias("tag_oi_flush"),
            (pl.col("basis_regime") == "premium_extreme").alias("tag_perp_premium_extreme"),
            (pl.col("basis_regime") == "discount_extreme").alias("tag_perp_discount_extreme"),
            pl.concat_str([
                pl.col("trend_regime"),
                pl.col("volatility_regime"),
                pl.col("funding_regime"),
                pl.col("oi_regime"),
                pl.col("basis_regime"),
            ], separator="|").alias("market_regime_tags"),
        ]
    )


__all__ = [
    "add_basis_regime",
    "add_funding_regime",
    "add_oi_regime",
    "add_regime_features",
    "add_trend_regime",
    "add_volatility_regime",
]
