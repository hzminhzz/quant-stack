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

def load_data():
    data_files = sorted(Path("Data/Binance").glob("BTC_1m_*.parquet"))
    dfs = [pl.read_parquet(f) for f in data_files]
    raw_df = pl.concat(dfs).sort("timestamp")
    df_dt = raw_df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("timestamp"))
    return resample_ohlcv(df_dt, every="4h")

def build_context_features(df: pl.DataFrame) -> pl.DataFrame:
    """Add deterministic context features using Polars only."""
    return df.sort("timestamp").with_columns(
        returns = pl.col("close").pct_change().fill_null(0)
    ).with_columns(
        rolling_vol = pl.col("returns").rolling_std(window_size=20),
    ).with_columns(
        rolling_vol_mean = pl.col("rolling_vol").rolling_mean(window_size=100),
        rolling_vol_std = pl.col("rolling_vol").rolling_std(window_size=100),
    ).with_columns(
        volatility_zscore = (pl.col("rolling_vol") - pl.col("rolling_vol_mean")) / pl.col("rolling_vol_std"),
        sma_20 = pl.col("close").rolling_mean(window_size=20),
        sma_50 = pl.col("close").rolling_mean(window_size=50)
    ).with_columns(
        trend_strength = (pl.col("sma_20") > pl.col("sma_50")).cast(pl.Int32),
        # Synthetic intelligence (Deterministic mock)
        liquidity_stress = (pl.col("volatility_zscore") > 3.0).cast(pl.Int32), # Extreme vol as proxy
        positive_funding_extreme = (pl.col("rsi") > 80).cast(pl.Int32), # High RSI as proxy
        negative_funding_extreme = (pl.col("rsi") < 20).cast(pl.Int32)  # Low RSI as proxy
    )

def apply_filters(df: pl.DataFrame, filter_id: str, params: Dict[str, Any] = None) -> pl.DataFrame:
    """Apply post-signal gating: filtered_signal = raw_signal if allowed else 0."""
    df = df.with_columns(allowed = pl.lit(1))
    
    if filter_id == "unfiltered_champion":
        pass
    elif filter_id == "volatility_extreme_disable":
        threshold = params.get("zscore_threshold", 2.5)
        df = df.with_columns(allowed = pl.when(pl.col("volatility_zscore") <= threshold).then(1).otherwise(0))
    elif filter_id == "moderate_volatility_only":
        min_z = params.get("min_zscore", -1.0)
        max_z = params.get("max_zscore", 2.0)
        df = df.with_columns(allowed = pl.when(pl.col("volatility_zscore").is_between(min_z, max_z)).then(1).otherwise(0))
    elif filter_id == "trend_strength_filter":
        df = df.with_columns(allowed = pl.col("trend_strength"))
    elif filter_id == "liquidity_stress_disable":
        df = df.with_columns(allowed = pl.when(pl.col("liquidity_stress") == 0).then(1).otherwise(0))
    elif filter_id == "funding_crowding_filter":
        # For longs: block if positive_funding_extreme
        # For shorts: block if negative_funding_extreme
        df = df.with_columns(
            allowed = pl.when((pl.col("signal") > 0) & (pl.col("positive_funding_extreme") == 1)).then(0)
                        .when((pl.col("signal") < 0) & (pl.col("negative_funding_extreme") == 1)).then(0)
                        .otherwise(1)
        )
    elif filter_id == "simple_combined_filter":
        # Combination of vol, liquidity, and funding
        df = df.with_columns(
            allowed = pl.when(
                (pl.col("volatility_zscore") <= 2.5) & 
                (pl.col("liquidity_stress") == 0) &
                ~((pl.col("signal") > 0) & (pl.col("positive_funding_extreme") == 1)) &
                ~((pl.col("signal") < 0) & (pl.col("negative_funding_extreme") == 1))
            ).then(1).otherwise(0)
        )
    
    return df.with_columns(
        filtered_signal = (pl.col("signal") * pl.col("allowed")).cast(pl.Int32)
    ).drop("signal").rename({"filtered_signal": "signal"})

def run_validation():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_momentum_context_validation.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/btc_4h_rsi_momentum_context_validation_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    df_4h = load_data()
    
    # 2. Champion Signal Generation
    cp = config["champion_parameters"]
    params = RSIMomentumParams(**cp)
    df_raw = build_signals(df_4h, params, variant="neutral-exit")
    
    # 3. Add Context
    df_context = build_context_features(df_raw)
    
    bt_cfg = config["backtest"]
    cost_model = CostModel(fee_rate=bt_cfg["fee_bps"]/10000.0, slippage_rate=bt_cfg["slippage_bps"]/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    
    results = []
    
    # 4. Filter Loop
    for f_cfg in config["filters"]:
        f_id = f_cfg["id"]
        print(f"Validating filter: {f_id}")
        
        df_filtered = apply_filters(df_context, f_id, f_cfg.get("params", {}))
        
        # Split into walk-forward windows or just run full period with window reporting
        res = backtester.run(df_filtered)
        
        # Calculate retention
        orig_trades = (df_raw.select(pl.col("signal") != 0).sum().item())
        new_trades = (df_filtered.select(pl.col("signal") != 0).sum().item())
        retention = float(new_trades / orig_trades) if orig_trades > 0 else 1.0
        
        results.append({
            "id": f_id,
            "name": f_cfg["name"],
            "metrics": res.metrics,
            "retention": retention
        })
        
        if f_id == "unfiltered_champion":
            with open(artifact_dir / "champion_unfiltered_metrics.json", "w") as f:
                json.dump(res.metrics, f, indent=2)

    # 5. Scoring
    champ = next(r for r in results if r["id"] == "unfiltered_champion")
    scored_results = []
    for r in results:
        score = 0
        reasons = []
        
        if r["metrics"]["smart_sharpe"] > champ["metrics"]["smart_sharpe"]:
            score += 1
            reasons.append("Sharpe improved")
        
        if r["metrics"]["max_drawdown"] > champ["metrics"]["max_drawdown"]: # DD is negative
            score += 1
            reasons.append("Max DD improved")
            
        if r["retention"] >= 0.4:
            score += 1
            reasons.append(f"Trade retention ({r['retention']:.1%}) >= 40%")
        else:
            score -= 1
            reasons.append(f"Trade retention ({r['retention']:.1%}) too low")
            
        classification = "reject_filter"
        if "Synthetic" in r["name"]:
            classification = "promising_but_needs_real_context_data"
        elif score >= 2:
            classification = "accept_filter_candidate"
        elif score >= 0:
            classification = "keep_unfiltered_champion"
            
        r["score"] = score
        r["classification"] = classification
        r["reasons"] = reasons
        scored_results.append(r)

    # 6. Artifacts
    with open(artifact_dir / "filtered_variant_metrics.json", "w") as f:
        json.dump(scored_results, f, indent=2)
        
    best_candidate = max([r for r in scored_results if r["id"] != "unfiltered_champion"], key=lambda x: x["score"])
    with open(artifact_dir / "selected_filter_candidate.json", "w") as f:
        json.dump(best_candidate, f, indent=2)

    # 7. Report.md
    report_md = f"""# RSI Momentum Context Validation Report (Phase 18C)
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Champion Parameters (Retained)
- Period: 14
- Upper: 70
- Lower: 30
- Exit: 50

## Filter Comparison
| Filter | Sharpe | Max DD | Retention | Classification |
|--------|--------|--------|-----------|----------------|
"""
    for r in scored_results:
        report_md += f"| {r['name']} | {r['metrics']['smart_sharpe']:.2f} | {r['metrics']['max_drawdown']:.2%} | {r['retention']:.1%} | {r['classification']} |\n"

    report_md += f"""
## Conclusion
Best Filter Candidate: **{best_candidate['name']}**
Classification: **{best_candidate['classification'].upper()}**

**Note**: Prior holdout was inspected in Phase 18B; Phase 18C conclusions are research-validation evidence.
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Validation complete. Best Candidate: {best_candidate['name']}")

if __name__ == "__main__":
    run_validation()
