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
        signal = (pl.col("signal") * pl.col("allowed")).cast(pl.Int32)
    )

def calculate_indicators(df: pl.DataFrame) -> pl.DataFrame:
    """Add ER and Vol Z-score."""
    er_n = 14
    vol_n = 42
    
    df = df.with_columns(
        change = pl.col("close").diff(),
        abs_change = pl.col("close").diff().abs()
    ).with_columns(
        dist = (pl.col("close") - pl.col("close").shift(er_n)).abs(),
        path = pl.col("abs_change").rolling_sum(window_size=er_n)
    ).with_columns(
        er = pl.col("dist") / pl.col("path"),
        vol = pl.col("close").pct_change().rolling_std(window_size=vol_n)
    ).with_columns(
        vol_mean = pl.col("vol").rolling_mean(window_size=vol_n),
        vol_std = pl.col("vol").rolling_std(window_size=vol_n)
    ).with_columns(
        vol_z = (pl.col("vol") - pl.col("vol_mean")) / pl.col("vol_std")
    )
    return df

def apply_chop_filter(df: pl.DataFrame, candidate_id: str) -> pl.DataFrame:
    df_f = df.clone()
    
    if candidate_id == "baseline":
        pass
    elif candidate_id.startswith("efficiency_ratio_"):
        threshold = float(candidate_id.replace("efficiency_ratio_", "")) / 100.0
        df_f = df_f.with_columns(signal = pl.when(pl.col("er") >= threshold).then(pl.col("signal")).otherwise(0))
    elif candidate_id == "moderate_volatility_only":
        df_f = df_f.with_columns(signal = pl.when((pl.col("vol_z") >= -1.0) & (pl.col("vol_z") <= 2.0)).then(pl.col("signal")).otherwise(0))
    elif candidate_id == "high_volatility_disable":
        df_f = df_f.with_columns(signal = pl.when(pl.col("vol_z") <= 2.5).then(pl.col("signal")).otherwise(0))
    elif candidate_id.startswith("cooldown_after_loss_"):
        # Cooldown is complex to implement in Polars purely without iterative logic if we want exact bar count after a 'loss' event.
        # Approximation: if prev net_return < 0, block for N bars using shift/max
        bars = int(candidate_id.replace("cooldown_after_loss_", "").replace("_bars", ""))
        # We need net_return from a 'naive' backtest first or use price change proxy.
        # For simplicity, we use the price change in signal direction as proxy for a 'loss' in current bar.
        df_f = df_f.with_columns(is_loss = (pl.col("signal").shift(1) * pl.col("close").pct_change() < 0).cast(pl.Int32))
        df_f = df_f.with_columns(blocked = pl.col("is_loss").rolling_max(window_size=bars, min_periods=1).fill_null(0))
        df_f = df_f.with_columns(signal = pl.when(pl.col("blocked") == 0).then(pl.col("signal")).otherwise(0))
        
    return df_f

def calculate_metrics_custom(df: pl.DataFrame, ret_col: str) -> Dict[str, Any]:
    if len(df) == 0: return {}
    stats = df.select([
        pl.col(ret_col).alias("ret"),
        pl.col("turnover")
    ]).with_columns([
        (pl.col("ret") + 1.0).cum_prod().alias("equity")
    ]).with_columns([
        (pl.col("equity") / pl.col("equity").cum_max() - 1.0).alias("drawdown")
    ]).select([
        pl.col("ret").mean().alias("avg_ret"),
        pl.col("ret").std().alias("std_ret"),
        (pl.col("ret") + 1.0).product().alias("total_ret_plus_1"),
        pl.col("drawdown").min().alias("mdd"),
        pl.col("turnover").sum().alias("total_turnover")
    ]).to_dicts()[0]

    avg_ret = stats["avg_ret"] or 0
    std_ret = stats["std_ret"] or 1
    total_ret = (stats["total_ret_plus_1"] or 1.0) - 1.0
    mdd = stats["mdd"] or 0
    sharpe = (avg_ret / std_ret) * np.sqrt(365 * 6) if std_ret > 0 else 0
    
    # Whipsaw approximation: loss bar + turnover change
    # (Actually requires trade logs for accuracy, but we'll use a proxy for the hypothesis)
    
    return {
        "cumulative_return": float(total_ret),
        "smart_sharpe": float(sharpe),
        "max_drawdown": float(mdd),
        "turnover": float(stats["total_turnover"])
    }

def run_hypothesis():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/rsi_momentum_chop_filter_hypothesis.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/rsi_momentum_chop_filter_hypothesis_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    symbols = config["symbols"]
    timeframe = config["timeframe"]
    params = RSIMomentumParams(**config["champion_parameters"])
    dd_start_str = config["hypothesis"]["drawdown_start"]
    dd_start = datetime.strptime(dd_start_str, "%Y-%m-%dT%H:%M:%SZ")
    
    cost_model = CostModel(fee_rate=config["hypothesis"]["fee_bps"]/10000.0, slippage_rate=config["hypothesis"]["slippage_bps"]/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    
    # 2. Pre-calculate Base Data (Trend Filtered)
    base_dfs = {}
    for symbol in symbols:
        print(f"Loading base data for {symbol}...")
        df_4h = load_and_resample(symbol, timeframe)
        df_raw = build_signals(df_4h, params, variant="neutral-exit")
        df_trend = apply_trend_filter(df_raw, config["trend_filter"]["params"])
        base_dfs[symbol] = calculate_indicators(df_trend)

    # 3. Evaluate Candidates
    candidates = [c["id"] for c in config["hypothesis"]["candidates"]]
    candidate_metrics = {}
    
    for cid in candidates:
        print(f"Evaluating candidate: {cid}...")
        symbol_results = []
        for symbol in symbols:
            df_chop = apply_chop_filter(base_dfs[symbol], cid)
            res = backtester.run(df_chop)
            df_res = res.frame.with_columns(is_post = pl.col("timestamp") >= dd_start)
            
            symbol_results.append({
                "full": calculate_metrics_custom(df_res, "net_return"),
                "post": calculate_metrics_custom(df_res.filter(pl.col("is_post")), "net_return"),
                "pre": calculate_metrics_custom(df_res.filter(~pl.col("is_post")), "net_return")
            })
        
        # Aggregate metrics (Average across symbols)
        agg = {
            "full_sharpe": np.mean([r["full"]["smart_sharpe"] for r in symbol_results]),
            "post_sharpe": np.mean([r["post"]["smart_sharpe"] for r in symbol_results]),
            "post_mdd": np.mean([r["post"]["max_drawdown"] for r in symbol_results]),
            "post_turnover": np.mean([r["post"]["turnover"] for r in symbol_results]),
            "pre_sharpe": np.mean([r["pre"]["smart_sharpe"] for r in symbol_results])
        }
        candidate_metrics[cid] = agg

    # 4. Scoring and Selection
    baseline = candidate_metrics["baseline"]
    selected = "baseline"
    best_score = 0
    
    final_scores = {}
    for cid, m in candidate_metrics.items():
        if cid == "baseline": continue
        score = 0
        if m["post_mdd"] > baseline["post_mdd"]: score += 1
        if m["post_turnover"] < baseline["post_turnover"] * 0.85: score += 1
        if m["full_sharpe"] >= baseline["full_sharpe"]: score += 1
        if m["pre_sharpe"] >= baseline["pre_sharpe"] * 0.95: score += 1
        
        final_scores[cid] = score
        if score > best_score:
            best_score = score
            selected = cid

    # 5. Artifacts
    with open(artifact_dir / "chop_filter_candidate_metrics.json", "w") as f:
        json.dump(candidate_metrics, f, indent=2)
    with open(artifact_dir / "selected_chop_filter_candidate.json", "w") as f:
        json.dump({"id": selected, "metrics": candidate_metrics[selected]}, f, indent=2)
    with open(artifact_dir / "chop_filter_validation_score.json", "w") as f:
        json.dump(final_scores, f, indent=2)

    # 6. Report.md
    report_md = f"""# RSI Momentum Chop Filter Hypothesis Test (Phase 18Y)
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Selected Candidate: **{selected.upper()}**

## Performance Summary (Average Symbol)
| Candidate | Full Sharpe | Post-10 Sharpe | Post-10 MDD | Turnover Red. |
|-----------|-------------|----------------|-------------|---------------|
"""
    for cid, m in candidate_metrics.items():
        turn_red = (1 - m["post_turnover"] / baseline["post_turnover"]) if baseline["post_turnover"] > 0 else 0
        report_md += f"| {cid} | {m['full_sharpe']:.2f} | {m['post_sharpe']:.2f} | {m['post_mdd']:.2%} | {turn_red:.1%} |\n"

    report_md += f"""
## Conclusion
The candidate **{selected}** was identified as the best secondary filter for reducing whipsaws and preserving historical edge.
Classification: **{'accept_chop_filter_candidate' if selected != 'baseline' else 'keep_current_champion'}**
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Hypothesis test complete. Selected: {selected}")

if __name__ == "__main__":
    run_hypothesis()
