"""Smart DCA strategy placeholder signal construction.

Smart DCA is path-dependent, so this module intentionally exposes order
intent columns instead of pretending the strategy is a stateless signal stream.
"""

from __future__ import annotations

import polars as pl

from quant_stack.strategies.smart_dca.params import SmartDCAParams


def build_features(df: pl.DataFrame, params: SmartDCAParams) -> pl.DataFrame:
    """Build basic features for Smart DCA (mostly a pass-through)."""
    return df.sort("timestamp").with_columns(
        [
            pl.lit(params.contract_size).alias("dca_contract_size"),
        ]
    )


def build_signals(df: pl.DataFrame, params: SmartDCAParams) -> pl.DataFrame:
    """Build signals for Smart DCA (placeholder since it's stateful)."""
    return build_features(df, params).with_columns(pl.lit(None).cast(pl.Int8).alias("signal"))


__all__ = ["build_features", "build_signals"]
