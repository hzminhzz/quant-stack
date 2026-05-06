"""OI-confirmed trend continuation signal construction."""

from __future__ import annotations

import polars as pl

from quant_stack.strategies.oi_confirmed_trend.params import OIConfirmedTrendParams


def get_required_columns(params: OIConfirmedTrendParams) -> set[str]:
    required = {"timestamp", "close", "ema_20", "ema_dist_20", "trend_strength_50_200"}
    if params.use_context_filters and params.require_oi_expansion:
        required.add("oi_zscore_60")
    if params.use_context_filters and params.avoid_funding_extreme:
        required.add("funding_zscore_30")
    if params.use_context_filters and params.avoid_basis_extreme:
        required.add("basis_zscore_60")
    return required


def get_optional_columns(_: OIConfirmedTrendParams) -> set[str]:
    return {"oi_zscore_60", "oi_change_pct_5", "funding_zscore_30", "basis_zscore_60", "spread_bps"}


def validate_input_columns(df: pl.DataFrame, params: OIConfirmedTrendParams) -> None:
    schema = set(df.columns)

    required = {"timestamp", "close", "ema_20", "ema_dist_20", "trend_strength_50_200"}
    missing = required - schema
    if missing:
        missing_sorted = ", ".join(sorted(missing))
        raise ValueError(f"oi_confirmed_trend missing required columns: {missing_sorted}")

    if params.use_context_filters and params.require_oi_expansion:
        if "oi_zscore_60" not in schema and "oi_change_pct_5" not in schema:
            raise ValueError(
                "oi_confirmed_trend requires oi_zscore_60 or oi_change_pct_5 when "
                + "require_oi_expansion=True and use_context_filters=True"
            )

    if params.use_context_filters and params.avoid_funding_extreme and "funding_zscore_30" not in schema:
        raise ValueError("oi_confirmed_trend missing required columns: funding_zscore_30")

    if params.use_context_filters and params.avoid_basis_extreme and "basis_zscore_60" not in schema:
        raise ValueError("oi_confirmed_trend missing required columns: basis_zscore_60")


def build_features(df: pl.DataFrame, params: OIConfirmedTrendParams) -> pl.DataFrame:
    validate_input_columns(df, params)
    return df.sort("timestamp")


def build_signals(df: pl.DataFrame, params: OIConfirmedTrendParams) -> pl.DataFrame:
    features = build_features(df, params)
    columns = set(features.columns)

    long_setup = (
        (pl.col("trend_strength_50_200") > params.trend_strength_threshold)
        & (pl.col("ema_dist_20") > params.min_ema_dist_20)
        & (pl.col("close") > pl.col("ema_20"))
    )

    context_pass = pl.lit(True)
    reason_oi_confirmation = pl.lit(True)
    if params.use_context_filters and params.require_oi_expansion:
        oi_conditions: list[pl.Expr] = []
        if "oi_zscore_60" in columns:
            oi_conditions.append(pl.col("oi_zscore_60") > params.oi_zscore_threshold)
        if "oi_change_pct_5" in columns:
            oi_conditions.append(pl.col("oi_change_pct_5") > params.oi_change_pct_threshold)
        reason_oi_confirmation = pl.any_horizontal(oi_conditions)
        context_pass = context_pass & reason_oi_confirmation

    reason_funding_extreme = pl.lit(True)
    if params.use_context_filters and params.avoid_funding_extreme:
        reason_funding_extreme = pl.col("funding_zscore_30") < params.funding_crowded_threshold
        context_pass = context_pass & reason_funding_extreme

    reason_liquidity_filter = pl.lit(True)
    if params.use_context_filters and params.avoid_basis_extreme:
        reason_liquidity_filter = pl.col("basis_zscore_60") < params.basis_crowded_threshold
        context_pass = context_pass & reason_liquidity_filter

    if params.max_spread_bps is not None and "spread_bps" in columns:
        context_pass = context_pass & (pl.col("spread_bps") <= params.max_spread_bps)

    long_setup = (long_setup & context_pass).fill_null(False)

    short_setup = (
        (pl.col("trend_strength_50_200") < -params.trend_strength_threshold)
        & (pl.col("close") < pl.col("ema_20"))
        & reason_oi_confirmation
    ).fill_null(False)

    exit_signal = (pl.col("close") < pl.col("ema_20")).fill_null(False) if params.exit_on_trend_reversal else pl.lit(False)

    return features.with_columns(
        [
            long_setup.alias("long_setup"),
            short_setup.alias("short_setup"),
            context_pass.fill_null(False).alias("context_filter_passed"),
            reason_oi_confirmation.fill_null(False).alias("reason_oi_confirmation"),
            reason_funding_extreme.fill_null(False).alias("reason_funding_extreme"),
            reason_liquidity_filter.fill_null(False).alias("reason_liquidity_filter"),
            long_setup.alias("entry_signal"),
            exit_signal.alias("exit_signal"),
        ]
    ).with_columns(
        pl.when(pl.col("entry_signal"))
        .then(pl.lit(1, dtype=pl.Int8))
        .when(pl.col("exit_signal"))
        .then(pl.lit(0, dtype=pl.Int8))
        .otherwise(pl.lit(None, dtype=pl.Int8))
        .alias("signal")
    )


__all__ = [
    "build_features",
    "build_signals",
    "get_optional_columns",
    "get_required_columns",
    "validate_input_columns",
]
