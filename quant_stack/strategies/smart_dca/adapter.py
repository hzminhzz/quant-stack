"""Adapter and execution functions for Smart DCA."""

from __future__ import annotations

import numpy as np
import polars as pl

from quant_stack.strategies.smart_dca.params import SmartDCAParams
from quant_stack.strategies.smart_dca.simulator import SmartDCAArrayContract, simulate_smart_dca, simulate_smart_dca_contract


def prepare_from_polars(
    df: pl.DataFrame, *, bid_col: str = "bid", ask_col: str = "ask", time_col: str = "timestamp"
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract required numpy arrays from Polars DataFrame."""
    return (
        df[time_col].to_numpy(),
        df[bid_col].to_numpy().astype(np.float64),
        df[ask_col].to_numpy().astype(np.float64),
    )


def run_smart_dca_backtest(
    df: pl.DataFrame,
    cfg: SmartDCAParams,
    *,
    time_col: str = "timestamp",
    bid_col: str = "bid",
    ask_col: str = "ask",
) -> dict[str, np.ndarray]:
    """
    Run Smart DCA backtest from a Polars DataFrame.

    Requires `bid_col` and `ask_col` in the DataFrame. If you only have `close`
    and `spread`, build the columns beforehand.

    Returns the simulation dictionary containing equity curve and trade logs.
    """
    timestamps, bid, ask = prepare_from_polars(
        df, bid_col=bid_col, ask_col=ask_col, time_col=time_col
    )
    return simulate_smart_dca(timestamps, bid, ask, cfg)


def run_smart_dca_backtest_contract(
    df: pl.DataFrame,
    cfg: SmartDCAParams,
    *,
    time_col: str = "timestamp",
    bid_col: str = "bid",
    ask_col: str = "ask",
    extra_trade_capacity: int = 0,
) -> SmartDCAArrayContract:
    """Run Smart DCA and return the preallocated output contract."""

    timestamps, bid, ask = prepare_from_polars(
        df, bid_col=bid_col, ask_col=ask_col, time_col=time_col
    )
    return simulate_smart_dca_contract(
        timestamps,
        bid,
        ask,
        cfg,
        extra_trade_capacity=extra_trade_capacity,
    )


__all__ = ["prepare_from_polars", "run_smart_dca_backtest", "run_smart_dca_backtest_contract"]
