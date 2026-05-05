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
    # Select only OHLCV to avoid schema mismatch (Datetime precision)
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
        signal = (pl.col("signal") * pl.col("allowed")).cast(pl.Int32)
    )

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

def run_attribution():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/rsi_momentum_post_2025_10_drawdown_attribution.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/rsi_momentum_post_2025_10_drawdown_attribution_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    symbols = config["symbols"]
    timeframe = config["timeframe"]
    params = RSIMomentumParams(**config["champion_parameters"])
    dd_start_str = config["diagnostic"]["drawdown_start"]
    dd_start = datetime.strptime(dd_start_str, "%Y-%m-%dT%H:%M:%SZ")
    
    cost_model = CostModel(fee_rate=config["diagnostic"]["fee_bps"]/10000.0, slippage_rate=config["diagnostic"]["slippage_bps"]/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    
    # 2. Loop symbols and collect results
    symbol_results = {}
    coverage = {}
    
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        df_4h = load_and_resample(symbol, timeframe)
        coverage[symbol] = {
            "start": str(df_4h["timestamp"].min()),
            "end": str(df_4h["timestamp"].max()),
            "count": len(df_4h)
        }
        
        df_raw = build_signals(df_4h, params, variant="neutral-exit")
        df_filtered = apply_trend_filter(df_raw, config["trend_filter"]["params"])
        res = backtester.run(df_filtered)
        
        # Segment data
        df_res = res.frame.with_columns(is_post = pl.col("timestamp") >= dd_start)
        pre = df_res.filter(~pl.col("is_post"))
        post = df_res.filter(pl.col("is_post"))
        
        symbol_results[symbol] = {
            "pre": calculate_metrics(pre, "net_return"),
            "post": calculate_metrics(post, "net_return"),
            "post_long_ret": post.filter(pl.col("position") > 0)["net_return"].sum() if len(post) > 0 else 0,
            "post_short_ret": post.filter(pl.col("position") < 0)["net_return"].sum() if len(post) > 0 else 0,
            "post_turnover": post["turnover"].sum() if len(post) > 0 else 0,
            "post_cost_drag": post["cost_return"].sum() if len(post) > 0 else 0,
            "post_vol": post["net_return"].std() if len(post) > 1 else 0
        }

    # 3. Portfolio Attribution (EW)
    # We need aligned returns
    # Simplified: Use sum of symbol contributions
    total_post_ret = sum([v["post"]["cumulative_return"] for v in symbol_results.values()]) / len(symbols)
    
    # 4. Failure Mode Logic
    classification = "normal_drawdown_within_expected_range"
    reasons = []
    
    for s, v in symbol_results.items():
        if v["post"]["cumulative_return"] < -0.05:
            reasons.append(f"{s} negative return")
            if v["post_cost_drag"] > abs(v["post"]["cumulative_return"]) * 0.5:
                classification = "cost_turnover_drag"
            elif abs(v["post_short_ret"]) > abs(v["post_long_ret"]):
                classification = "short_side_failure"
            else:
                classification = "market_regime_shift_to_chop"

    failure_mode = {
        "classification": classification,
        "reasons": reasons,
        "symbol_details": symbol_results
    }
    
    # 5. Artifacts
    with open(artifact_dir / "data_coverage_summary.json", "w") as f:
        json.dump(coverage, f, indent=2)
    with open(artifact_dir / "pre_post_2025_10_metrics.json", "w") as f:
        json.dump(symbol_results, f, indent=2)
    with open(artifact_dir / "failure_mode_classification.json", "w") as f:
        json.dump(failure_mode, f, indent=2)
        
    # 6. Report.md
    report_md = f"""# RSI Momentum Drawdown Attribution (Phase 18X)
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Observed Issue
Strategy underperformance starting {dd_start_str}.

## Classification: **{classification.upper()}**

## Pre/Post Comparison
| Symbol | Pre Sharpe | Post Sharpe | Post Return | Cost Drag |
|--------|------------|-------------|-------------|-----------|
"""
    for s, v in symbol_results.items():
        report_md += f"| {s} | {v['pre'].get('smart_sharpe',0):.2f} | {v['post'].get('smart_sharpe',0):.2f} | {v['post'].get('cumulative_return',0):.2%} | {v['post_cost_drag']:.2%} |\n"

    report_md += f"""
## Summary
{classification.capitalize()}. {', '.join(reasons)}.
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Attribution complete. Classification: {classification}")

if __name__ == "__main__":
    run_attribution()
