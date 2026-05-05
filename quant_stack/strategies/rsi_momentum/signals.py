"""RSI Momentum signal construction with multiple variants."""

from __future__ import annotations
import polars as pl
from quant_stack.indicators.polars.momentum import rsi
from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams

def build_features(df: pl.DataFrame, params: RSIMomentumParams) -> pl.DataFrame:
    """Add RSI feature to the dataframe."""
    return df.sort("timestamp").with_columns(
        rsi(window=params.rsi_period, alias="rsi")
    )

def build_signals(df: pl.DataFrame, params: RSIMomentumParams, variant: str = "neutral-exit") -> pl.DataFrame:
    """Build raw desired position signal for the specified variant.
    
    IMPORTANT: We do NOT shift the signal here. The engine handles one-bar lag.
    """
    df = build_features(df, params)
    
    if variant == "neutral-exit":
        # RSI extreme momentum neutral-exit version
        # Long entry: RSI >= 70, Long exit: RSI < 50
        # Short entry: RSI <= 30, Short exit: RSI > 50
        return df.with_columns(
            long_comp = pl.when(pl.col("rsi") >= params.rsi_upper).then(1)
                        .when(pl.col("rsi") < params.rsi_exit).then(0)
                        .otherwise(None).forward_fill().fill_null(0),
            short_comp = pl.when(pl.col("rsi") <= params.rsi_lower).then(-1)
                         .when(pl.col("rsi") > params.rsi_exit).then(0)
                         .otherwise(None).forward_fill().fill_null(0)
        ).with_columns(
            signal = (pl.col("long_comp") + pl.col("short_comp")).cast(pl.Int32)
        )
    
    elif variant == "extreme-zone":
        # RSI extreme-zone exposure (long if >70, short if <30, else flat)
        return df.with_columns(
            signal = pl.when(pl.col("rsi") >= params.rsi_upper).then(1)
                     .when(pl.col("rsi") <= params.rsi_lower).then(-1)
                     .otherwise(0).cast(pl.Int32)
        )
    
    elif variant == "always-in":
        # RSI always-in-market flip
        return df.with_columns(
            signal = pl.when(pl.col("rsi") >= params.rsi_upper).then(1)
                     .when(pl.col("rsi") <= params.rsi_lower).then(-1)
                     .otherwise(None).forward_fill().fill_null(0).cast(pl.Int32)
        )
    
    elif variant == "mean-reversion":
        # Classic RSI mean-reversion baseline
        return df.with_columns(
            long_comp = pl.when(pl.col("rsi") <= params.rsi_lower).then(1)
                        .when(pl.col("rsi") >= params.rsi_exit).then(0)
                        .otherwise(None).forward_fill().fill_null(0),
            short_comp = pl.when(pl.col("rsi") >= params.rsi_upper).then(-1)
                         .when(pl.col("rsi") <= params.rsi_exit).then(0)
                         .otherwise(None).forward_fill().fill_null(0)
        ).with_columns(
            signal = (pl.col("long_comp") + pl.col("short_comp")).cast(pl.Int32)
        )

    elif variant == "long-flat":
        # RSI momentum long-flat (long if >= 70, flat if < 50, ignore shorts)
        return df.with_columns(
            signal = pl.when(pl.col("rsi") >= params.rsi_upper).then(1)
                     .when(pl.col("rsi") < params.rsi_exit).then(0)
                     .otherwise(None).forward_fill().fill_null(0).cast(pl.Int32)
        )

    elif variant == "buy-and-hold":
        return df.with_columns(signal = pl.lit(1).cast(pl.Int32))
    
    elif variant == "flat":
        return df.with_columns(signal = pl.lit(0).cast(pl.Int32))
        
    else:
        raise ValueError(f"Unknown variant: {variant}")

__all__ = ["build_features", "build_signals"]
