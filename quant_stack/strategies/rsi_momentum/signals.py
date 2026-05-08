"""RSI Momentum signal construction with multiple variants."""

from __future__ import annotations
import polars as pl
from quant_stack.indicators.polars.momentum import rsi
from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams


def _bollinger_bands(close: pl.Series, period: int, num_std: float) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Calculate Bollinger Bands: middle, upper, lower."""
    rolling = close.rolling_mean(period)
    std = close.rolling_std(period)
    upper = rolling + (std * num_std)
    lower = rolling - (std * num_std)
    return rolling, upper, lower


def _calculate_bb_width(df: pl.DataFrame, params: RSIMomentumParams) -> pl.DataFrame:
    df = df.sort("timestamp")
    middle, upper, lower = _bollinger_bands(
        df["close"], params.bb_period, params.bb_std
    )
    bb_width = (upper - lower) / middle
    df = df.with_columns(bb_width.alias("bb_width"))
    lookback = params.bb_width_lookback
    percentile = params.bb_width_percentile
    threshold = bb_width.rolling_quantile(quantile=percentile, window_size=lookback, interpolation="nearest")
    df = df.with_columns(threshold.alias("bb_width_threshold"))
    df = df.with_columns(
        pl.when(pl.col("bb_width") <= pl.col("bb_width_threshold"))
        .then(True)
        .otherwise(False)
        .alias("bb_squeeze_active")
    )
    return df


def build_features(df: pl.DataFrame, params: RSIMomentumParams) -> pl.DataFrame:
    df = df.sort("timestamp").with_columns(
        rsi(window=params.rsi_period, alias="rsi")
    )
    if params.use_bb_filter:
        df = _calculate_bb_width(df, params)
    return df


def build_signals(df: pl.DataFrame, params: RSIMomentumParams, variant: str = "neutral-exit") -> pl.DataFrame:
    df = build_features(df, params)
    
    if variant == "neutral-exit":
        if params.use_bb_filter:
            filtered_long = pl.when(
                (pl.col("rsi") >= params.rsi_upper) & (pl.col("bb_squeeze_active") == True)
            ).then(1).when(pl.col("rsi") < params.rsi_exit).then(0).otherwise(None).forward_fill().fill_null(0)
            
            filtered_short = pl.when(
                (pl.col("rsi") <= params.rsi_lower) & (pl.col("bb_squeeze_active") == True)
            ).then(-1).when(pl.col("rsi") > params.rsi_exit).then(0).otherwise(None).forward_fill().fill_null(0)
            
            return df.with_columns(
                long_comp = filtered_long,
                short_comp = filtered_short,
                signal = (filtered_long + filtered_short).cast(pl.Int32)
            )
        else:
            long_comp = pl.when(pl.col("rsi") >= params.rsi_upper).then(1) \
                .when(pl.col("rsi") < params.rsi_exit).then(0) \
                .otherwise(None).forward_fill().fill_null(0)
            short_comp = pl.when(pl.col("rsi") <= params.rsi_lower).then(-1) \
                .when(pl.col("rsi") > params.rsi_exit).then(0) \
                .otherwise(None).forward_fill().fill_null(0)
            return df.with_columns(
                long_comp = long_comp,
                short_comp = short_comp,
                signal = (long_comp + short_comp).cast(pl.Int32)
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
