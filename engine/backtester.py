"""
engine/backtester.py
Canonical Numba-JIT SMA + RSI crossover backtester.
This is the SINGLE SOURCE OF TRUTH for all strategy simulation in the pipeline.
Every file that needs backtesting imports from here.
"""
import numpy as np
from numba import njit


@njit
def get_equity_and_trades_rsi(
    close_prices: np.ndarray,
    short_window: int,
    long_window: int,
    rsi_period: int,
    rsi_threshold: float,
    rsi_side: str = "below",  # "below" for dip-buying, "above" for momentum
    fee_pct: float = 0.0005,  # 0.05% standard fee
):
    """
    SMA crossover with RSI confirmation filter.
    Returns (equity_curve, is_exposed, trade_returns_array).

    - equity_curve: normalized equity starting at 1.0
    - is_exposed: boolean mask of when position is open
    - trade_returns: array of per-trade returns (for Monte Carlo)
    """
    n = len(close_prices)
    equity = np.ones(n, dtype=np.float64)
    is_exposed = np.zeros(n, dtype=np.bool_)

    trade_returns_buffer = np.zeros(n // 2, dtype=np.float64)
    num_trades = 0

    max_lookback = max(long_window, rsi_period + 1)
    if n <= max_lookback:
        return equity, is_exposed, np.zeros(0, dtype=np.float64)

    position = 0
    entry_price = 0.0
    current_equity = 1.0

    # Pre-compute gain/loss arrays for RSI
    gains = np.zeros(n)
    losses = np.zeros(n)

    for i in range(1, n):
        diff = close_prices[i] - close_prices[i - 1]
        if diff > 0:
            gains[i] = diff
        else:
            losses[i] = -diff

    avg_gain = np.mean(gains[1 : rsi_period + 1])
    avg_loss = np.mean(losses[1 : rsi_period + 1])

    # Initialize running SMA sums
    short_sum = np.sum(close_prices[max_lookback - short_window : max_lookback])
    long_sum = np.sum(close_prices[max_lookback - long_window : max_lookback])

    for i in range(max_lookback, n):
        equity[i] = current_equity

        # Wilder smoothed RSI update
        avg_gain = ((avg_gain * (rsi_period - 1)) + gains[i]) / rsi_period
        avg_loss = ((avg_loss * (rsi_period - 1)) + losses[i]) / rsi_period

        rs = avg_gain / avg_loss if avg_loss > 0 else 0
        rsi = 100.0 - (100.0 / (1.0 + rs)) if avg_loss > 0 else 100.0

        # Running SMA values
        prev_short_sma = short_sum / short_window
        prev_long_sma = long_sum / long_window

        short_sum += close_prices[i] - close_prices[i - short_window]
        long_sum += close_prices[i] - close_prices[i - long_window]

        curr_short_sma = short_sum / short_window
        curr_long_sma = long_sum / long_window

        crosses_above = prev_short_sma <= prev_long_sma and curr_short_sma > curr_long_sma
        crosses_below = prev_short_sma >= prev_long_sma and curr_short_sma < curr_long_sma

        # Entry Condition based on RSI Side
        rsi_condition = (rsi > rsi_threshold) if rsi_side == "above" else (rsi < rsi_threshold)

        if position == 0 and crosses_above and rsi_condition:
            position = 1
            entry_price = close_prices[i]
            # Pay entry fee
            current_equity *= (1.0 - fee_pct)
            is_exposed[i] = True

        elif position == 1 and crosses_below:
            trade_return = (close_prices[i] - entry_price) / entry_price
            current_equity *= (1.0 + trade_return)
            # Pay exit fee
            current_equity *= (1.0 - fee_pct)
            equity[i] = current_equity
            is_exposed[i] = True
            position = 0

            trade_returns_buffer[num_trades] = trade_return
            num_trades += 1

        elif position == 1:
            floating_pnl = (close_prices[i] - entry_price) / entry_price
            equity[i] = current_equity * (1.0 + floating_pnl)
            is_exposed[i] = True

    return equity, is_exposed, trade_returns_buffer[:num_trades]
