import numpy as np
from numba import njit

@njit
def run_monte_carlo(trade_returns: np.ndarray, num_simulations: int = 1000, seed: int = 42):
    """
    Shuffles trade returns 'num_simulations' times to simulate alternate realities.
    Returns (mc_max_drawdown_95, mc_median_drawdown) as negative floats.
    """
    if len(trade_returns) == 0:
        return 0.0, 0.0

    np.random.seed(seed)
    
    num_trades = len(trade_returns)
    drawdowns = np.zeros(num_simulations)
    
    for i in range(num_simulations):
        shuffled_returns = np.copy(trade_returns)
        np.random.shuffle(shuffled_returns)
        
        peak_equity = 1.0
        current_equity = 1.0
        max_dd = 0.0
        
        for j in range(num_trades):
            current_equity *= (1.0 + shuffled_returns[j])
            if current_equity > peak_equity:
                peak_equity = current_equity
            
            dd = (peak_equity - current_equity) / peak_equity
            if dd > max_dd:
                max_dd = dd
                
        drawdowns[i] = max_dd
        
    drawdowns = np.sort(drawdowns)
    idx_95 = int(num_simulations * 0.95)
    mc_max_drawdown_95 = drawdowns[idx_95] * -1.0
    
    idx_50 = int(num_simulations * 0.50)
    mc_median_drawdown = drawdowns[idx_50] * -1.0
    
    return mc_max_drawdown_95, mc_median_drawdown
