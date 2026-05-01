"""
engine/grid_backtester.py
Performance-optimized backtester for Dynamic Boundary Grid strategies.
Equity-Adaptive Sizing to prevent leverage-induced bankruptcy.
"""
import numpy as np
from numba import njit

@njit
def simulate_dynamic_grid(
    close_prices: np.ndarray,
    num_levels: int,
    grid_width_pct: float,
    fee_pct: float = 0.0002,
    initial_capital: float = 10000.0
):
    n = len(close_prices)
    equity = np.zeros(n, dtype=np.float64)
    equity[0] = initial_capital
    
    cash = initial_capital
    position = 0.0 
    
    # State variables
    center_price = close_prices[0]
    upper_boundary = center_price * (1.0 + grid_width_pct / 2.0)
    lower_boundary = center_price * (1.0 - grid_width_pct / 2.0)
    
    levels = np.linspace(lower_boundary, upper_boundary, num_levels)
    # level_qtys[j]: quantity of asset held at level j
    level_qtys = np.zeros(num_levels, dtype=np.float64)
    
    current_equity = initial_capital

    for i in range(1, n):
        price = close_prices[i]
        prev_price = close_prices[i-1]
        
        # Adaptive qty: total exposure = current_equity
        level_qty_usd = current_equity / num_levels if current_equity > 0 else 0

        # 1. Boundary Breach -> Re-center
        if price > upper_boundary or price < lower_boundary:
            if position != 0:
                cash += position * price
                cash -= abs(position * price) * fee_pct
                position = 0.0
                level_qtys.fill(0.0)
            
            center_price = price
            upper_boundary = center_price * (1.0 + grid_width_pct / 2.0)
            lower_boundary = center_price * (1.0 - grid_width_pct / 2.0)
            levels = np.linspace(lower_boundary, upper_boundary, num_levels)
            
        # 2. Normal Grid Execution
        else:
            for j in range(num_levels):
                level_price = levels[j]
                
                # Zone: BELOW center -> Long Grid
                if level_price < center_price:
                    # Crossed downward -> Buy (Open Long)
                    if prev_price > level_price and price <= level_price:
                        if level_qtys[j] == 0:
                            qty = level_qty_usd / level_price
                            cash -= qty * level_price * (1.0 + fee_pct)
                            position += qty
                            level_qtys[j] = qty
                    # Crossed upward -> Sell (Close Long)
                    elif prev_price < level_price and price >= level_price:
                        if level_qtys[j] > 0:
                            qty = level_qtys[j]
                            cash += qty * level_price * (1.0 - fee_pct)
                            position -= qty
                            level_qtys[j] = 0.0
                            
                # Zone: ABOVE center -> Short Grid
                elif level_price > center_price:
                    # Crossed upward -> Sell (Open Short)
                    if prev_price < level_price and price >= level_price:
                        if level_qtys[j] == 0:
                            qty = level_qty_usd / level_price
                            cash += qty * level_price * (1.0 - fee_pct)
                            position -= qty
                            level_qtys[j] = -qty # Store as negative to indicate short
                    # Crossed downward -> Buy (Close Short)
                    elif prev_price > level_price and price <= level_price:
                        if level_qtys[j] < 0:
                            qty = -level_qtys[j] # Use positive qty for buy-back
                            cash -= qty * level_price * (1.0 + fee_pct)
                            position += qty
                            level_qtys[j] = 0.0
        
        # 3. Update Equity
        current_equity = cash + position * price
        if current_equity <= 0:
            current_equity = 0
            equity[i:] = 0
            break
        equity[i] = current_equity
        
    return equity

def calculate_grid_metrics(equity_curve):
    valid_equity = equity_curve[equity_curve > 0]
    if len(valid_equity) < 2:
        return {"Total Return": -1.0, "Max Drawdown": -1.0, "Sharpe Ratio": 0.0}
        
    returns = np.diff(equity_curve) / np.where(equity_curve[:-1] > 0, equity_curve[:-1], 1.0)
    returns = returns[equity_curve[:-1] > 0]
    
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 24 * 60) if len(returns) > 0 and np.std(returns) > 0 else 0
    
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peak) / np.where(peak > 0, peak, 1.0)
    max_dd = np.min(drawdowns)
    
    total_return = (equity_curve[-1] / equity_curve[0]) - 1
    
    return {
        "Total Return": total_return,
        "Max Drawdown": max_dd,
        "Sharpe Ratio": sharpe
    }
