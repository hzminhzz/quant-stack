"""RSI Momentum Ensemble Strategy."""

from __future__ import annotations

import polars as pl
from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams
from quant_stack.strategies.rsi_momentum.signals import build_signals as rsi_build_signals


def _volatility_scaling(df: pl.DataFrame, window: int = 20, target_vol: float = 0.02) -> pl.DataFrame:
    """Calculate volatility-based position scaling."""
    returns = df['close'].pct_change().abs()
    vol = returns.rolling_mean(window)
    scale = (target_vol / vol).fill_null(1.0).clip(0.25, 1.0)
    return df.with_columns(scale.alias('vol_scale'))


def build_ensemble_signals(
    df: pl.DataFrame,
    variants: list[dict],
    blend_method: str = "vote",
    use_vol_scaling: bool = True,
) -> pl.DataFrame:
    """Build ensemble signal from multiple RSI variants.
    
    Args:
        df: OHLCV data
        variants: List of param dicts for each variant
        blend_method: "vote" (majority wins) or "average" (mean signal)
        use_vol_scaling: Apply volatility-based position sizing
    
    Returns:
        DataFrame with ensemble_signal column
    """
    df = df.sort("timestamp")
    all_signals = []
    
    for variant_params in variants:
        params = RSIMomentumParams(**variant_params)
        signals = rsi_build_signals(df, params, variant="neutral-exit")
        all_signals.append(signals['signal'])
    
    if blend_method == "vote":
        avg = sum(all_signals) / len(all_signals)
        ensemble = avg.round().cast(pl.Int32)
    else:
        avg = sum(all_signals) / len(all_signals)
        ensemble = avg.round().clip(-1, 1).cast(pl.Int32)
    
    df = df.with_columns(ensemble.alias('ensemble_signal'))
    
    if use_vol_scaling:
        df = _volatility_scaling(df)
        df = df.with_columns(
            (pl.col('ensemble_signal') * pl.col('vol_scale')).alias('signal')
        )
    else:
        df = df.with_columns(pl.col('ensemble_signal').alias('signal'))
    
    return df


# Define ensemble variants
ENSEMBLE_VARIANTS = [
    # Baseline - works in bull markets
    {"rsi_period": 14, "rsi_upper": 70, "rsi_lower": 30, "rsi_exit": 50, "use_bb_filter": False},
    # SOL-optimized - works in declining markets  
    {"rsi_period": 14, "rsi_upper": 75, "rsi_lower": 25, "rsi_exit": 55, "use_bb_filter": False},
    # Conservative - slower RSI
    {"rsi_period": 21, "rsi_upper": 70, "rsi_lower": 30, "rsi_exit": 50, "use_bb_filter": False},
    # Aggressive - faster RSI
    {"rsi_period": 7, "rsi_upper": 75, "rsi_lower": 25, "rsi_exit": 50, "use_bb_filter": False},
]

__all__ = ["build_ensemble_signals", "ENSEMBLE_VARIANTS"]