"""Derivatives-context features from funding, OI, and basis columns."""

from __future__ import annotations

import polars as pl

from quant_stack.features.schemas import FeatureThresholdConfig, FeatureWindowConfig


def add_funding_features(df: pl.DataFrame, window: int, threshold: float, allow_missing: bool) -> pl.DataFrame:
    if "funding_rate" not in df.columns:
        if allow_missing:
            return df
        raise ValueError("funding_rate column is required when allow_missing=False")

    mean = pl.col("funding_rate").rolling_mean(window_size=window, min_samples=window)
    std = pl.col("funding_rate").rolling_std(window_size=window, min_samples=window)
    out = df.with_columns(((pl.col("funding_rate") - mean) / std).alias(f"funding_zscore_{window}"))
    q90 = pl.col("funding_rate").rolling_quantile(0.9, window_size=90, min_samples=30)
    out = out.with_columns((pl.col("funding_rate") >= q90).cast(pl.Float64).alias("funding_percentile_90"))
    z = pl.col(f"funding_zscore_{window}")
    return out.with_columns(
        [
            (z > threshold).alias("funding_positive_extreme"),
            (z < -threshold).alias("funding_negative_extreme"),
            ((z.shift(1).abs() > threshold) & (z.abs() < 0.5)).alias("funding_reset"),
        ]
    )


def add_open_interest_features(df: pl.DataFrame, window: int, threshold: float, allow_missing: bool) -> pl.DataFrame:
    if "open_interest" not in df.columns:
        if allow_missing:
            return df
        raise ValueError("open_interest column is required when allow_missing=False")

    out = df.with_columns(
        [
            pl.col("open_interest").diff().alias("oi_change_1"),
            pl.col("open_interest").diff(5).alias("oi_change_5"),
            pl.col("open_interest").pct_change(5).alias("oi_change_pct_5"),
        ]
    )
    mean = pl.col("open_interest").rolling_mean(window_size=window, min_samples=window)
    std = pl.col("open_interest").rolling_std(window_size=window, min_samples=window)
    out = out.with_columns(((pl.col("open_interest") - mean) / std).alias(f"oi_zscore_{window}"))
    z = pl.col(f"oi_zscore_{window}")
    return out.with_columns(
        [
            ((z > threshold) | (pl.col("oi_change_pct_5") > 0.03)).alias("oi_expansion"),
            ((z < -threshold) | (pl.col("oi_change_pct_5") < -0.03)).alias("oi_flush"),
        ]
    )


def add_basis_features(df: pl.DataFrame, window: int, threshold: float, allow_missing: bool) -> pl.DataFrame:
    if "basis" not in df.columns:
        if allow_missing:
            return df
        raise ValueError("basis column is required when allow_missing=False")

    mean = pl.col("basis").rolling_mean(window_size=window, min_samples=window)
    std = pl.col("basis").rolling_std(window_size=window, min_samples=window)
    out = df.with_columns(((pl.col("basis") - mean) / std).alias(f"basis_zscore_{window}"))
    q90 = pl.col("basis").rolling_quantile(0.9, window_size=90, min_samples=30)
    out = out.with_columns((pl.col("basis") >= q90).cast(pl.Float64).alias("basis_percentile_90"))
    z = pl.col(f"basis_zscore_{window}")
    return out.with_columns(
        [
            (z > threshold).alias("perp_premium_extreme"),
            (z < -threshold).alias("perp_discount_extreme"),
        ]
    )


def add_derivatives_features(
    df: pl.DataFrame,
    config: FeatureWindowConfig,
    thresholds: FeatureThresholdConfig,
    *,
    allow_missing: bool,
) -> pl.DataFrame:
    out = add_funding_features(
        df,
        window=config.zscore_windows.get("funding", 30),
        threshold=thresholds.funding_zscore_extreme,
        allow_missing=allow_missing,
    )
    out = add_open_interest_features(
        out,
        window=config.zscore_windows.get("oi", 60),
        threshold=thresholds.oi_zscore_extreme,
        allow_missing=allow_missing,
    )
    out = add_basis_features(
        out,
        window=config.zscore_windows.get("basis", 60),
        threshold=thresholds.basis_zscore_extreme,
        allow_missing=allow_missing,
    )
    return out


__all__ = [
    "add_basis_features",
    "add_derivatives_features",
    "add_funding_features",
    "add_open_interest_features",
]
