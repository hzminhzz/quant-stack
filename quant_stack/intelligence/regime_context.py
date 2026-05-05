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


__all__ = ["context_columns", "optimizer_context_filter"]
