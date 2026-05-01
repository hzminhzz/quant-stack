"""
engine/backtester_bb.py
Numba-JIT Bollinger Band Breakout Backtester.
Strategy:
- Long Entry: Price > Upper Band (20, 1) AND Price > SMA(200).
- Exit: Price < SMA(20) (Middle Band).
- Friction: 0.15% per side (fees + slippage).
"""
import numpy as np
from numba import njit


@njit
def get_equity_and_trades_bb(
    close_prices: np.ndarray,
    bb_length: int = 20,
    bb_std: float = 1.0,
    regime_sma_length: int = 200,
    friction: float = 0.0015,  # 0.15% per side
):
    n = len(close_prices)
    equity = np.ones(n, dtype=np.float64)
    is_exposed = np.zeros(n, dtype=np.bool_)
    trade_returns_buffer = np.zeros(n // 2, dtype=np.float64)
    num_trades = 0

    max_lookback = max(bb_length, regime_sma_length)
    if n <= max_lookback:
        return equity, is_exposed, np.zeros(0, dtype=np.float64)

    position = 0
    entry_price = 0.0
    current_equity = 1.0

    # Initialize running sums for SMA(20) and SMA(200)
    bb_sum = np.sum(close_prices[max_lookback - bb_length : max_lookback])
    regime_sum = np.sum(close_prices[max_lookback - regime_sma_length : max_lookback])

    for i in range(max_lookback, n):
        equity[i] = current_equity

        # BB Middle (SMA 20)
        ma_20 = bb_sum / bb_length
        # BB Standard Deviation
        variance = 0.0
        for j in range(i - bb_length, i):
            diff = close_prices[j] - ma_20
            variance += diff * diff
        std = np.sqrt(variance / bb_length)
        
        upper_band = ma_20 + (bb_std * std)
        regime_ma = regime_sum / regime_sma_length

        price = close_prices[i]

        # Entry Logic: Breakout above Upper Band + Above 200 SMA
        if position == 0 and price > upper_band and price > regime_ma:
            position = 1
            entry_price = price
            # Pay entry friction
            current_equity *= (1.0 - friction)
            is_exposed[i] = True

        # Exit Logic: Cross below Middle Band
        elif position == 1 and price < ma_20:
            trade_return = (price - entry_price) / entry_price
            current_equity *= (1.0 + trade_return)
            # Pay exit friction
            current_equity *= (1.0 - friction)
            equity[i] = current_equity
            is_exposed[i] = True
            position = 0

            trade_returns_buffer[num_trades] = trade_return
            num_trades += 1

        elif position == 1:
            floating_pnl = (price - entry_price) / entry_price
            equity[i] = current_equity * (1.0 + floating_pnl)
            is_exposed[i] = True

        # Update running sums
        bb_sum += close_prices[i] - close_prices[i - bb_length]
        regime_sum += close_prices[i] - close_prices[i - regime_sma_length]

    return equity, is_exposed, trade_returns_buffer[:num_trades]
