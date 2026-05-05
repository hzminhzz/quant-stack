import os
import json
import yaml
import polars as pl
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams
from quant_stack.strategies.rsi_momentum.signals import build_signals
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.backtesting.costs import CostModel
from quant_stack.data.resample import resample_ohlcv

def load_and_resample(symbol: str, timeframe: str = "4h") -> pl.DataFrame:
    """Load 1m data for a symbol and resample to timeframe."""
    prefix = symbol.split("-")[0]
    data_files = sorted(Path("Data/Binance").glob(f"{prefix}_1m_*.parquet"))
    if not data_files:
        raise FileNotFoundError(f"No 1m data for {symbol}")
        
    dfs = [pl.read_parquet(f).select(["timestamp", "open", "high", "low", "close", "volume"]) for f in data_files]
    raw_df = pl.concat(dfs).sort("timestamp")
    df_dt = raw_df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("timestamp"))
    
    # Resample
    df_resampled = resample_ohlcv(df_dt, every=timeframe)
    return df_resampled

def apply_trend_filter(df: pl.DataFrame, params: Dict[str, Any]) -> pl.DataFrame:
    """Reproduce Phase 18C Trend Strength Filter: SMA 20 > SMA 50."""
    fast = params.get("sma_period_fast", 20)
    slow = params.get("sma_period_slow", 50)
    
    df = df.with_columns(
        sma_fast = pl.col("close").rolling_mean(window_size=fast),
        sma_slow = pl.col("close").rolling_mean(window_size=slow)
    ).with_columns(
        allowed = (pl.col("sma_fast") > pl.col("sma_slow")).cast(pl.Int32)
    )
    
    return df.with_columns(
        filtered_signal = (pl.col("signal") * pl.col("allowed")).cast(pl.Int32)
    ).drop("signal").rename({"filtered_signal": "signal"})

def run_generalization():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/rsi_momentum_trend_filter_multisymbol.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/rsi_momentum_multisymbol_generalization_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    symbols = config["symbols"]
    timeframe = config["timeframe"]
    cp = config["champion_parameters"]
    params = RSIMomentumParams(**cp)
    
    bt_cfg = config["backtest"]
    cost_model = CostModel(fee_rate=bt_cfg["fee_bps"]/10000.0, slippage_rate=bt_cfg["slippage_bps"]/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    
    symbol_metrics_unfiltered = {}
    symbol_metrics_filtered = {}
    symbol_metrics_bh = {}
    
    coverage_summary = {}

    # 2. Per-Symbol Loop
    for symbol in symbols:
        print(f"Processing symbol: {symbol}")
        try:
            df_4h = load_and_resample(symbol, timeframe)
            coverage_summary[symbol] = {
                "start": str(df_4h["timestamp"].min()),
                "end": str(df_4h["timestamp"].max()),
                "rows": len(df_4h)
            }
        except Exception as e:
            print(f"Skipping {symbol}: {e}")
            continue
            
        # A. Buy and Hold
        df_bh = build_signals(df_4h, params, variant="buy-and-hold")
        res_bh = backtester.run(df_bh)
        symbol_metrics_bh[symbol] = res_bh.metrics
        
        # B. Unfiltered Champion
        df_raw = build_signals(df_4h, params, variant="neutral-exit")
        res_unfiltered = backtester.run(df_raw)
        symbol_metrics_unfiltered[symbol] = res_unfiltered.metrics
        
        # C. Trend Filtered Champion
        df_context = df_raw.clone() # Signals already in df_raw
        df_filtered = apply_trend_filter(df_context, config["trend_filter"]["params"])
        res_filtered = backtester.run(df_filtered)
        symbol_metrics_filtered[symbol] = res_filtered.metrics

    # 3. Artifacts
    with open(artifact_dir / "data_coverage_summary.json", "w") as f:
        json.dump(coverage_summary, f, indent=2)
        
    with open(artifact_dir / "symbol_metrics_unfiltered.json", "w") as f:
        json.dump(symbol_metrics_unfiltered, f, indent=2)
        
    with open(artifact_dir / "symbol_metrics_trend_filtered.json", "w") as f:
        json.dump(symbol_metrics_filtered, f, indent=2)
        
    with open(artifact_dir / "symbol_benchmark_metrics.json", "w") as f:
        json.dump(symbol_metrics_bh, f, indent=2)

    # 4. Scoring
    score = 0
    reasons = []
    
    for s in symbols:
        if s not in symbol_metrics_filtered: continue
        
        m_f = symbol_metrics_filtered[s]
        m_u = symbol_metrics_unfiltered[s]
        m_b = symbol_metrics_bh[s]
        
        if m_f["cumulative_return"] > 0:
            score += 1
            reasons.append(f"{s} positive OOS return")
            
        if m_f["smart_sharpe"] > m_u["smart_sharpe"]:
            score += 1
            reasons.append(f"{s} filter improves Sharpe")
            
    avg_sharpe = np.mean([m["smart_sharpe"] for m in symbol_metrics_filtered.values()])
    
    classification = "promising_but_mixed"
    if score >= 4: classification = "generalizes"
    elif score <= 1: classification = "btc_only"
    
    gen_score = {
        "score": score,
        "classification": classification,
        "reasons": reasons,
        "average_sharpe": float(avg_sharpe)
    }
    with open(artifact_dir / "generalization_score.json", "w") as f:
        json.dump(gen_score, f, indent=2)

    # 5. Report.md
    report_md = f"""# RSI Momentum Multi-Symbol Generalization Report (Phase 18D)
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary
Classification: **{classification.upper()}**

## Per-Symbol Metrics (Filtered)
| Symbol | Return | Sharpe | Max DD | vs B&H Sharpe |
|--------|--------|--------|--------|---------------|
"""
    for s in symbols:
        if s not in symbol_metrics_filtered: continue
        m = symbol_metrics_filtered[s]
        mb = symbol_metrics_bh[s]
        report_md += f"| {s} | {m['cumulative_return']:.2%} | {m['smart_sharpe']:.2f} | {m['max_drawdown']:.2%} | {mb['smart_sharpe']:.2f} |\n"

    report_md += f"""
## Conclusion
{classification.capitalize()}. {', '.join(reasons)}.
Average Filtered Sharpe: {avg_sharpe:.2f}
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Generalization complete. Classification: {classification}")

if __name__ == "__main__":
    run_generalization()
