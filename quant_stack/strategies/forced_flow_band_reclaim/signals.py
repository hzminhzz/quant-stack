"""Forced-flow proxy band reclaim signal construction."""

from __future__ import annotations

import polars as pl

from quant_stack.strategies.forced_flow_band_reclaim.params import ForcedFlowBandReclaimParams


def get_required_columns(params: ForcedFlowBandReclaimParams) -> set[str]:
    reclaim_column = "bb_reclaim_lower_strict" if params.use_strict_reclaim else "bb_reclaim_lower"
    required = {"timestamp", "close", "bb_mid_20", "bb_lower_20", reclaim_column}
    if params.use_context_filters and params.require_oi_flush:
        required.add("oi_flush")
    if params.use_context_filters and params.require_funding_filter:
        required.add("funding_zscore_30")
    if params.use_context_filters and params.require_basis_filter:
        required.add("basis_zscore_60")
    return required


def get_optional_columns(_: ForcedFlowBandReclaimParams) -> set[str]:
    optional = {
        "bb_reclaim_lower",
        "bb_reclaim_lower_strict",
        "bb_reclaim_upper",
        "bb_reclaim_upper_strict",
        "liquidation_proxy_long",
        "forced_selling_proxy",
        "liquidation_proxy_short",
        "forced_buying_proxy",
        "oi_flush",
        "funding_zscore_30",
        "basis_zscore_60",
        "spread_bps",
    }
    return optional


def validate_input_columns(df: pl.DataFrame, params: ForcedFlowBandReclaimParams) -> None:
    schema = set(df.columns)
    missing = get_required_columns(params) - schema
    if missing:
        missing_sorted = ", ".join(sorted(missing))
        raise ValueError(f"forced_flow_band_reclaim missing required columns: {missing_sorted}")

    if params.use_context_filters and params.require_forced_flow_proxy:
        if "liquidation_proxy_long" not in schema and "forced_selling_proxy" not in schema:
            raise ValueError(
                "forced_flow_band_reclaim requires liquidation_proxy_long or forced_selling_proxy when "
                + "require_forced_flow_proxy=True and use_context_filters=True"
            )


def build_features(df: pl.DataFrame, params: ForcedFlowBandReclaimParams) -> pl.DataFrame:
    validate_input_columns(df, params)
    return df.sort("timestamp")


def build_signals(df: pl.DataFrame, params: ForcedFlowBandReclaimParams) -> pl.DataFrame:
    features = build_features(df, params)
    columns = set(features.columns)

    reclaim_col = "bb_reclaim_lower_strict" if params.use_strict_reclaim and "bb_reclaim_lower_strict" in columns else "bb_reclaim_lower"
    long_setup = pl.col(reclaim_col).fill_null(False)

    context_pass = pl.lit(True)
    if params.use_context_filters and params.require_forced_flow_proxy:
        forced_flow_exprs: list[pl.Expr] = []
        if "liquidation_proxy_long" in columns:
            forced_flow_exprs.append(pl.col("liquidation_proxy_long").fill_null(False))
        if "forced_selling_proxy" in columns:
            forced_flow_exprs.append(pl.col("forced_selling_proxy").fill_null(False))
        context_pass = context_pass & pl.any_horizontal(forced_flow_exprs)

    if params.use_context_filters and params.require_oi_flush:
        context_pass = context_pass & pl.col("oi_flush").fill_null(False)

    if params.use_context_filters and params.require_funding_filter:
        context_pass = context_pass & (pl.col("funding_zscore_30") <= 0)

    if params.use_context_filters and params.require_basis_filter:
        context_pass = context_pass & (pl.col("basis_zscore_60") <= 0)

    if params.max_spread_bps is not None and "spread_bps" in columns:
        context_pass = context_pass & (pl.col("spread_bps") <= params.max_spread_bps)

    long_setup = (long_setup & context_pass).fill_null(False)

    short_setup_components: list[pl.Expr] = []
    if params.use_strict_reclaim and "bb_reclaim_upper_strict" in columns:
        short_setup_components.append(pl.col("bb_reclaim_upper_strict").fill_null(False))
    elif "bb_reclaim_upper" in columns:
        short_setup_components.append(pl.col("bb_reclaim_upper").fill_null(False))
    if "liquidation_proxy_short" in columns:
        short_setup_components.append(pl.col("liquidation_proxy_short").fill_null(False))
    if "forced_buying_proxy" in columns:
        short_setup_components.append(pl.col("forced_buying_proxy").fill_null(False))
    short_setup = pl.any_horizontal(short_setup_components) if short_setup_components else pl.lit(False)

    exit_signal = (pl.col("close") >= pl.col("bb_mid_20")).fill_null(False) if params.exit_at_mid_band else pl.lit(False)

    return features.with_columns(
        [
            long_setup.alias("long_setup"),
            short_setup.alias("short_setup"),
            context_pass.fill_null(False).alias("context_filter_passed"),
            long_setup.alias("reason_forced_flow"),
            long_setup.alias("entry_signal"),
            exit_signal.alias("exit_signal"),
        ]
    ).with_columns(
        pl.when(pl.col("long_setup"))
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
