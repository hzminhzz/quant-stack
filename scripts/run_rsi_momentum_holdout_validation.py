import os
import json
import yaml
import polars as pl
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple

from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams
from quant_stack.strategies.rsi_momentum.signals import build_signals
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.backtesting.costs import CostModel
from quant_stack.data.resample import resample_ohlcv

def load_and_resample(symbol: str, timeframe: str = "4h") -> pl.DataFrame:
    prefix = symbol.split("-")[0]
    data_files = sorted(Path("Data/Binance").glob(f"{prefix}_1m_*.parquet"))
    if not data_files: raise FileNotFoundError(f"No 1m data for {symbol}")
    dfs = [pl.read_parquet(f).select(["timestamp", "open", "high", "low", "close", "volume"]) for f in data_files]
    raw_df = pl.concat(dfs).sort("timestamp")
    df_dt = raw_df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("timestamp"))
    return resample_ohlcv(df_dt, every=timeframe)

def apply_trend_filter(df: pl.DataFrame, params: Dict[str, Any]) -> pl.DataFrame:
    fast, slow = params.get("sma_period_fast", 20), params.get("sma_period_slow", 50)
    df = df.with_columns(
        sma_fast = pl.col("close").rolling_mean(window_size=fast),
        sma_slow = pl.col("close").rolling_mean(window_size=slow)
    ).with_columns(
        allowed = (pl.col("sma_fast") > pl.col("sma_slow")).cast(pl.Int32)
    )
    return df.with_columns(
        trend_signal = (pl.col("signal") * pl.col("allowed")).cast(pl.Int32)
    ).drop("signal").rename({"trend_signal": "signal"})

def apply_high_vol_disable(df: pl.DataFrame, threshold: float = 2.5) -> pl.DataFrame:
    vol_n = 42
    df = df.with_columns(
        vol = pl.col("close").pct_change().rolling_std(window_size=vol_n)
    ).with_columns(
        vol_mean = pl.col("vol").rolling_mean(window_size=vol_n, min_periods=1),
        vol_std = pl.col("vol").rolling_std(window_size=vol_n, min_periods=1)
    ).with_columns(
        vol_z = ((pl.col("vol") - pl.col("vol_mean")) / pl.col("vol_std")).fill_nan(0.0).fill_null(0.0)
    ).with_columns(
        vol_allowed = (pl.col("vol_z") <= threshold).cast(pl.Int32)
    )
    return df.with_columns(
        filtered_signal = (pl.col("signal") * pl.col("vol_allowed")).cast(pl.Int32)
    ).drop("signal").rename({"filtered_signal": "signal"})

def calculate_metrics(df: pl.DataFrame, ret_col: str) -> Dict[str, Any]:
    if len(df) == 0: return {}
    stats = df.select([
        pl.col(ret_col).alias("ret")
    ]).with_columns([
        (pl.col("ret") + 1.0).cum_prod().alias("equity")
    ]).with_columns([
        (pl.col("equity") / pl.col("equity").cum_max() - 1.0).alias("drawdown")
    ]).select([
        pl.col("ret").mean().alias("avg_ret"),
        pl.col("ret").std().alias("std_ret"),
        (pl.col("ret") + 1.0).product().alias("total_ret_plus_1"),
        pl.col("drawdown").min().alias("mdd")
    ]).to_dicts()[0]

    avg_ret = stats["avg_ret"] or 0
    std_ret = stats["std_ret"] or 1
    total_ret = (stats["total_ret_plus_1"] or 1.0) - 1.0
    mdd = stats["mdd"] or 0
    sharpe = (avg_ret / std_ret) * np.sqrt(365 * 6) if std_ret > 0 else 0
    
    return {
        "cumulative_return": float(total_ret),
        "smart_sharpe": float(sharpe),
        "max_drawdown": float(mdd)
    }

def run_validation():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/rsi_momentum_holdout_validation.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/rsi_momentum_holdout_validation_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    holdout_symbols = config["holdout_symbols"]
    core_symbols = config["core_symbols"]
    timeframe = config["timeframe"]
    params = RSIMomentumParams(**config["champion_parameters"])
    fwd_start = datetime.strptime(config["validation"]["forward_start"], "%Y-%m-%dT%H:%M:%SZ")
    
    cost_model = CostModel(fee_rate=config["validation"]["fee_bps"]/10000.0, slippage_rate=config["validation"]["slippage_bps"]/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    
    holdout_results = {}
    forward_results = {}

    # 2. Independent Asset Holdout (SOL, ADA)
    for symbol in holdout_symbols:
        print(f"Validating holdout asset: {symbol}")
        df_4h = load_and_resample(symbol, timeframe)
        
        # Baseline (SMA only)
        df_raw = build_signals(df_4h, params, variant="neutral-exit")
        df_baseline = apply_trend_filter(df_raw.clone(), config["trend_filter"]["params"])
        res_baseline = backtester.run(df_baseline)
        
        # Enhanced (SMA + Vol Disable)
        df_enhanced = apply_high_vol_disable(df_baseline.clone(), config["chop_filter"]["params"]["threshold"])
        res_enhanced = backtester.run(df_enhanced)
        
        holdout_results[symbol] = {
            "baseline": calculate_metrics(res_baseline.frame, "net_return"),
            "enhanced": calculate_metrics(res_enhanced.frame, "net_return")
        }

    # 3. Forward Data Validation (BTC, ETH, BNB - 2026)
    for symbol in core_symbols:
        print(f"Validating forward data for: {symbol}")
        df_4h = load_and_resample(symbol, timeframe)
        df_fwd = df_4h.filter(pl.col("timestamp") >= fwd_start)
        
        if len(df_fwd) < 10:
            print(f"Insufficient forward data for {symbol}, skipping.")
            continue
            
        df_raw = build_signals(df_fwd, params, variant="neutral-exit")
        df_baseline = apply_trend_filter(df_raw.clone(), config["trend_filter"]["params"])
        res_baseline = backtester.run(df_baseline)
        
        df_enhanced = apply_high_vol_disable(df_baseline.clone(), config["chop_filter"]["params"]["threshold"])
        res_enhanced = backtester.run(df_enhanced)
        
        forward_results[symbol] = {
            "baseline": calculate_metrics(res_baseline.frame, "net_return"),
            "enhanced": calculate_metrics(res_enhanced.frame, "net_return")
        }

    # 4. Artifacts
    with open(artifact_dir / "holdout_asset_metrics.json", "w") as f:
        json.dump(holdout_results, f, indent=2)
    with open(artifact_dir / "forward_data_metrics.json", "w") as f:
        json.dump(forward_results, f, indent=2)

    # 5. Report.md
    report_md = f"""# RSI Momentum Holdout Validation (Phase 18Z)
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Executive Summary
The `high_volatility_disable` filter was validated against independent assets (SOL, ADA) and forward data (2026).

## Holdout Asset Performance (SOL, ADA)
| Symbol | Baseline Sharpe | Enhanced Sharpe | MDD Improvement |
|--------|-----------------|-----------------|-----------------|
"""
    for s, v in holdout_results.items():
        m_b, m_e = v["baseline"], v["enhanced"]
        mdd_imp = (m_e["max_drawdown"] - m_b["max_drawdown"]) # MDD is negative, so enhanced - baseline
        report_md += f"| {s} | {m_b['smart_sharpe']:.2f} | {m_e['smart_sharpe']:.2f} | {mdd_imp:.2%} |\n"

    report_md += f"""
## Forward Data Performance (BTC, ETH, BNB 2026)
| Symbol | Baseline Sharpe | Enhanced Sharpe | MDD Improvement |
|--------|-----------------|-----------------|-----------------|
"""
    for s, v in forward_results.items():
        m_b, m_e = v["baseline"], v["enhanced"]
        mdd_imp = (m_e["max_drawdown"] - m_b["max_drawdown"])
        report_md += f"| {s} | {m_b['smart_sharpe']:.2f} | {m_e['smart_sharpe']:.2f} | {mdd_imp:.2%} |\n"

    avg_sharpe_b = np.mean([v["baseline"]["smart_sharpe"] for v in holdout_results.values()])
    avg_sharpe_e = np.mean([v["enhanced"]["smart_sharpe"] for v in holdout_results.values()])
    
    validation_status = "VALIDATED" if avg_sharpe_e > avg_sharpe_b else "FAILED"

    report_md += f"""
## Conclusion
Final Status: **{validation_status}**
Average Holdout Sharpe Improvement: {avg_sharpe_e - avg_sharpe_b:.2f}
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Holdout validation complete. Status: {validation_status}")

if __name__ == "__main__":
    run_validation()
