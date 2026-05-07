"""Helpers exposing intelligence context to research/optimizer consumers."""

from __future__ import annotations

import polars as pl


def context_columns() -> list[str]:
    return [
        "funding_rate",
        "open_interest",
        "basis_bps",
        "spread_bps",
        "depth_imbalance",
        "liquidation_imbalance",
    ]


def optimizer_context_filter(context_df: pl.DataFrame, *, max_spread_bps: float = 20.0, min_depth_imbalance: float = -1.0, max_depth_imbalance: float = 1.0) -> pl.DataFrame:
    if context_df.is_empty():
        return context_df
    conditions = [pl.col("spread_bps") <= max_spread_bps]
    if "depth_imbalance" in context_df.columns:
        conditions.append(pl.col("depth_imbalance").is_between(min_depth_imbalance, max_depth_imbalance, closed="both"))
    return context_df.filter(pl.all_horizontal(conditions))


def apply_context_gate_to_signals(
    signal_frame: pl.DataFrame,
    context_frame: pl.DataFrame,
    *,
    max_spread_bps: float,
    min_depth_imbalance: float = -1.0,
    max_depth_imbalance: float = 1.0,
    suppress_when_context_missing: bool = True,
) -> pl.DataFrame:
    if signal_frame.is_empty():
        return signal_frame

    gated = signal_frame.sort("timestamp").with_columns(pl.col("signal").alias("raw_signal"))

    if context_frame.is_empty():
        raw_context_gate_pass = pl.lit(not suppress_when_context_missing)
        context_gate_pass = pl.when(pl.col("raw_signal") == 1).then(raw_context_gate_pass).otherwise(True)
        return gated.with_columns(
            [
                context_gate_pass.alias("context_gate_pass"),
                pl.when((pl.col("raw_signal") == 1) & (~context_gate_pass))
                .then(pl.lit(None, dtype=gated.schema.get("signal", pl.Int8)))
                .otherwise(pl.col("raw_signal"))
                .alias("signal"),
            ]
        )

    rename_map = {
        column: ("context_timestamp" if column == "timestamp" else column)
        for column in context_frame.columns
    }
    joined = gated.join_asof(
        context_frame.sort("timestamp").rename(rename_map),
        left_on="timestamp",
        right_on="context_timestamp",
        strategy="backward",
    )

    checks: list[pl.Expr] = []
    availability_checks: list[pl.Expr] = []
    if "spread_bps" in joined.columns:
        checks.append(pl.col("spread_bps") <= max_spread_bps)
        availability_checks.append(pl.col("spread_bps").is_not_null())
    if "depth_imbalance" in joined.columns:
        checks.append(pl.col("depth_imbalance").is_between(min_depth_imbalance, max_depth_imbalance, closed="both"))
        availability_checks.append(pl.col("depth_imbalance").is_not_null())

    if checks:
        all_checks = pl.all_horizontal(checks).fill_null(False)
        all_available = pl.all_horizontal(availability_checks) if availability_checks else pl.lit(True)
        if suppress_when_context_missing:
            raw_context_gate_pass = (all_available & all_checks).fill_null(False)
        else:
            raw_context_gate_pass = pl.when(all_available).then(all_checks).otherwise(True).fill_null(False)
    else:
        raw_context_gate_pass = pl.lit(True)

    context_gate_pass = pl.when(pl.col("raw_signal") == 1).then(raw_context_gate_pass).otherwise(True)

    signal_dtype = joined.schema.get("signal", pl.Int8)
    return joined.with_columns(
        [
            context_gate_pass.alias("context_gate_pass"),
            pl.when((pl.col("raw_signal") == 1) & (~context_gate_pass))
            .then(pl.lit(None, dtype=signal_dtype))
            .otherwise(pl.col("raw_signal"))
            .alias("signal"),
        ]
    )


__all__ = ["apply_context_gate_to_signals", "context_columns", "optimizer_context_filter"]
