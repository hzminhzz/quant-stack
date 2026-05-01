import polars as pl
import numpy as np

def calculate_prop_metrics(df: pl.DataFrame, initial_capital: float = 100000) -> dict:
    """
    Computes Prop Firm analytics using 100% vectorized Polars expressions.
    Expects df with columns: 'timestamp' (datetime), 'equity' (float), 'is_exposed' (bool).
    """
    if len(df) == 0:
        return {}

    # Basic stats
    last_equity = df.select(pl.col("equity").last()).item()
    cumulative_return = (last_equity / initial_capital) - 1.0
    
    time_in_market = df.select(pl.col("is_exposed").mean()).item()
    
    # CAGR
    start_date = df.select(pl.col("timestamp").min()).item()
    end_date = df.select(pl.col("timestamp").max()).item()
    days_elapsed = (end_date - start_date).total_seconds() / 86400.0
    cagr = (last_equity / initial_capital) ** (365.0 / days_elapsed) - 1.0 if days_elapsed > 0 else 0.0

    # Max Drawdown
    df = df.with_columns(pl.col("equity").cum_max().alias("peak_equity"))
    max_drawdown = df.select(((pl.col("peak_equity") - pl.col("equity")) / pl.col("peak_equity")).max()).item() * -1.0

    # Daily aggregation for Prop Metrics
    # We group by date to find daily open, min, and close equity
    daily = df.group_by(pl.col("timestamp").dt.date()).agg([
        pl.col("equity").first().alias("open_eq"),
        pl.col("equity").min().alias("min_eq"),
        pl.col("equity").last().alias("close_eq")
    ]).sort("timestamp")
    
    # Calculate daily metrics
    daily = daily.with_columns([
        ((pl.col("min_eq") - pl.col("open_eq")) / pl.col("open_eq")).alias("daily_dd"),
        ((pl.col("close_eq") - pl.col("open_eq")) / pl.col("open_eq")).alias("daily_return")
    ])
    
    # Max Daily Drawdown
    max_daily_drawdown = daily.select(pl.col("daily_dd").min()).item()
    if max_daily_drawdown is None:
        max_daily_drawdown = 0.0
        
    # Max Consecutive Losing Days
    daily = daily.with_columns((pl.col("daily_return") < 0).cast(pl.Int32).alias("is_loss"))
    daily = daily.with_columns(
        (pl.col("is_loss") != pl.col("is_loss").shift(1)).fill_null(True).cum_sum().alias("streak_id")
    )
    streaks = daily.filter(pl.col("is_loss") == 1).group_by("streak_id").agg(pl.len().alias("streak_len"))
    max_losing_days = streaks.select(pl.col("streak_len").max()).item() if len(streaks) > 0 else 0

    # Risk Metrics (Smart Sharpe & Sortino)
    daily_returns = daily.select(pl.col("daily_return")).drop_nulls()
    
    if len(daily_returns) > 1:
        mean_ret = daily_returns.mean().item()
        std_ret = daily_returns.std().item()
        
        # Autocorrelation (lag 1)
        # Polars correlation of shifted series
        df_corr = daily_returns.with_columns(pl.col("daily_return").shift(1).alias("lag1")).drop_nulls()
        if len(df_corr) > 1 and df_corr.select(pl.col("daily_return").std()).item() > 0 and df_corr.select(pl.col("lag1").std()).item() > 0:
            auto_corr = df_corr.select(pl.corr("daily_return", "lag1")).item()
        else:
            auto_corr = 0.0
            
        auto_corr = 0.0 if np.isnan(auto_corr) else auto_corr
        
        adj_factor = np.sqrt((1 + auto_corr) / (1 - auto_corr)) if -1 < auto_corr < 1 else 1.0
        annualization_factor = np.sqrt(365)
        
        smart_sharpe = (mean_ret / std_ret) * annualization_factor / adj_factor if std_ret > 0 else 0.0
        
        downside = daily_returns.filter(pl.col("daily_return") < 0)
        downside_std = downside.std().item() if len(downside) > 1 else 0.0
        smart_sortino = (mean_ret / downside_std) * annualization_factor / adj_factor if downside_std > 0 else 0.0
        
        # Tail Ratio
        p95 = daily_returns.select(pl.col("daily_return").quantile(0.95)).item()
        p5 = daily_returns.select(pl.col("daily_return").quantile(0.05)).item()
        tail_ratio = abs(p95 / p5) if (p5 is not None and p5 != 0) else float('inf')
        
        # Gain/Pain Ratio
        _sum_gains = daily_returns.filter(pl.col("daily_return") > 0).sum().item()
        _sum_losses = daily_returns.filter(pl.col("daily_return") < 0).sum().item()
        sum_gains = _sum_gains if _sum_gains is not None else 0.0
        sum_losses = abs(_sum_losses) if _sum_losses is not None else 0.0
        gain_pain_ratio = sum_gains / sum_losses if sum_losses > 0 else float('inf')
        
        # Kelly Criterion
        n_wins = len(daily_returns.filter(pl.col("daily_return") > 0))
        win_rate = n_wins / len(daily_returns) if len(daily_returns) > 0 else 0.0
        _avg_win = daily_returns.filter(pl.col("daily_return") > 0).mean().item()
        _avg_loss = daily_returns.filter(pl.col("daily_return") < 0).mean().item()
        avg_win = _avg_win if _avg_win is not None else 0.0
        avg_loss = abs(_avg_loss) if _avg_loss is not None else 0.0
        
        if avg_loss > 0 and avg_win > 0:
            win_loss_ratio = avg_win / avg_loss
            kelly_criterion = win_rate - ((1.0 - win_rate) / win_loss_ratio) if win_loss_ratio > 0 else 0.0
        elif avg_loss == 0 and avg_win > 0:
            kelly_criterion = 1.0
        else:
            kelly_criterion = 0.0
    else:
        smart_sharpe = 0.0
        smart_sortino = 0.0
        tail_ratio = 0.0
        gain_pain_ratio = 0.0
        kelly_criterion = 0.0

    return {
        "cumulative_return": cumulative_return,
        "cagr": cagr,
        "time_in_market": time_in_market,
        "max_drawdown": max_drawdown,
        "max_daily_drawdown": max_daily_drawdown,
        "max_consecutive_losing_days": max_losing_days,
        "smart_sharpe": smart_sharpe,
        "smart_sortino": smart_sortino,
        "tail_ratio": tail_ratio,
        "gain_pain_ratio": gain_pain_ratio,
        "kelly_criterion": kelly_criterion
    }
