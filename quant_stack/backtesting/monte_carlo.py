"""Monte Carlo trade-return stress tests."""

from __future__ import annotations

import numpy as np


def run_monte_carlo(trade_returns: list[float] | np.ndarray, *, num_simulations: int = 1000, seed: int = 42) -> tuple[float, float]:
    returns = np.asarray(trade_returns, dtype=float)
    if len(returns) == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    drawdowns = np.zeros(num_simulations, dtype=float)
    for index in range(num_simulations):
        shuffled = rng.permutation(returns)
        equity = np.cumprod(1.0 + shuffled)
        peak = np.maximum.accumulate(equity)
        drawdowns[index] = np.max((peak - equity) / peak)
    return float(-np.quantile(drawdowns, 0.95)), float(-np.quantile(drawdowns, 0.50))


__all__ = ["run_monte_carlo"]
