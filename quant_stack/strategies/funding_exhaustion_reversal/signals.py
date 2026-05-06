"""Funding exhaustion reversal signal construction."""

from __future__ import annotations

import polars as pl

from quant_stack.strategies.funding_exhaustion_reversal.params import FundingExhaustionReversalParams


def get_required_columns(params: FundingExhaustionReversalParams) -> set[str]:
    required = {"timestamp", "rsi_14"}
    if params.use_context_filters:
        required.add("funding_zscore_30")
    if params.require_momentum_turn:
        required.add("momentum_slope_10")
    if params.require_basis_confirmation:
        required.add("basis_zscore_60")
    return required


def get_optional_columns(_: FundingExhaustionReversalParams) -> set[str]:
    return {
        "price_extension_20",
        "ret_60",
        "momentum_slope_10",
        "funding_zscore_30",
        "basis_zscore_60",
        "spread_bps",
    }


def validate_input_columns(df: pl.DataFrame, params: FundingExhaustionReversalParams) -> None:
    schema = set(df.columns)
    missing = get_required_columns(params) - schema
    if missing:
        missing_sorted = ", ".join(sorted(missing))
        raise ValueError(f"funding_exhaustion_reversal missing required columns: {missing_sorted}")

    if params.require_price_extension and "price_extension_20" not in schema and "ret_60" not in schema:
        raise ValueError("funding_exhaustion_reversal requires price_extension_20 or ret_60 when require_price_extension=True")


def build_features(df: pl.DataFrame, params: FundingExhaustionReversalParams) -> pl.DataFrame:
    validate_input_columns(df, params)
    return df.sort("timestamp")


def build_signals(df: pl.DataFrame, params: FundingExhaustionReversalParams) -> pl.DataFrame:
    features = build_features(df, params)
    columns = set(features.columns)

    long_setup = (pl.col("rsi_14") <= params.rsi_oversold)

    context_pass = pl.lit(True)
    if params.use_context_filters:
        context_pass = context_pass & (pl.col("funding_zscore_30") <= -params.funding_zscore_threshold)

    reason_price_extension = pl.lit(True)
    if params.require_price_extension:
        if "price_extension_20" in columns:
            reason_price_extension = pl.col("price_extension_20") <= -params.price_extension_threshold
        else:
            reason_price_extension = pl.col("ret_60") <= -params.price_extension_threshold
        context_pass = context_pass & reason_price_extension

    reason_momentum_turn = pl.lit(True)
    if params.require_momentum_turn:
        reason_momentum_turn = pl.col("momentum_slope_10") > 0
        context_pass = context_pass & reason_momentum_turn

    reason_funding_extreme = pl.lit(True)
    if params.use_context_filters:
        reason_funding_extreme = pl.col("funding_zscore_30") <= -params.funding_zscore_threshold

    if params.require_basis_confirmation:
        context_pass = context_pass & (pl.col("basis_zscore_60") <= -params.basis_zscore_threshold)

    if params.max_spread_bps is not None and "spread_bps" in columns:
        context_pass = context_pass & (pl.col("spread_bps") <= params.max_spread_bps)

    long_setup = (long_setup & context_pass).fill_null(False)

    short_setup = (
        (pl.col("rsi_14") >= params.rsi_overbought)
        & (
            (pl.col("funding_zscore_30") >= params.funding_zscore_threshold)
            if "funding_zscore_30" in columns
            else pl.lit(False)
        )
        & ((pl.col("momentum_slope_10") < 0) if "momentum_slope_10" in columns else pl.lit(False))
    ).fill_null(False)

    exit_signal = (pl.col("rsi_14") >= params.exit_rsi_midline).fill_null(False) if params.exit_on_rsi_midline else pl.lit(False)

    return features.with_columns(
        [
            long_setup.alias("long_setup"),
            short_setup.alias("short_setup"),
            context_pass.fill_null(False).alias("context_filter_passed"),
            reason_funding_extreme.fill_null(False).alias("reason_funding_extreme"),
            reason_price_extension.fill_null(False).alias("reason_liquidity_filter"),
            reason_momentum_turn.fill_null(False).alias("reason_oi_confirmation"),
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
