import os
import json
import yaml
import polars as pl
import numpy as np
from pathlib import Path
from datetime import datetime, date
from typing import Any, Dict, List

from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams
from quant_stack.strategies.rsi_momentum.signals import build_signals
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.backtesting.costs import CostModel
from quant_stack.data.resample import resample_ohlcv

def load_data():
    data_files = sorted(Path("Data/Binance").glob("BTC_1m_*.parquet"))
    dfs = []
    for f in data_files:
        dfs.append(pl.read_parquet(f))
    raw_df = pl.concat(dfs).sort("timestamp")
    df_dt = raw_df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("timestamp"))
    return resample_ohlcv(df_dt, every="4h")

def run_backtest(df: pl.DataFrame, params: RSIMomentumParams, variant: str, fee_bps: float, slippage_bps: float):
    cost_model = CostModel(fee_rate=fee_bps/10000.0, slippage_rate=slippage_bps/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    df_signals = build_signals(df, params, variant=variant)
    return backtester.run(df_signals)

def calculate_trade_distribution(res_df: pl.DataFrame):
    # Approximate trade distribution from position changes
    # A 'trade' starts when position != 0 and != prev_position
    # This is a simplification
    changes = res_df.with_columns(
        pos_change = (pl.col("position") != pl.col("position").shift(1)).fill_null(True)
    ).filter(pl.col("pos_change"))
    
    # We can't easily get exact trade returns without a loop or complex polars logic
    # but we can get average bars held etc.
    return {
        "approx_trade_count": len(changes),
        "turnover": float(res_df.select(pl.col("turnover").sum()).item())
    }

def run_robustness_audit():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_extreme_momentum_robustness.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/btc_4h_rsi_extreme_momentum_robustness_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    df_4h = load_data()
    
    def_params = config["default_parameters"]
    params = RSIMomentumParams(
        rsi_period=def_params["rsi_period"],
        rsi_upper=def_params["rsi_upper"],
        rsi_lower=def_params["rsi_lower"],
        rsi_exit=def_params["rsi_exit"]
    )
    
    bt_cfg = config["backtest"]
    
    # 1. Train/Test Split
    print("Running Train/Test Split...")
    split_ratio = config["audit"]["train_test_split"]
    split_idx = int(len(df_4h) * split_ratio)
    df_train = df_4h.head(split_idx)
    df_test = df_4h.tail(len(df_4h) - split_idx)
    
    res_train = run_backtest(df_train, params, "neutral-exit", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    res_test = run_backtest(df_test, params, "neutral-exit", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    
    train_test_metrics = {
        "train": res_train.metrics,
        "test": res_test.metrics,
        "gap": res_train.metrics["cumulative_return"] - res_test.metrics["cumulative_return"]
    }
    with open(artifact_dir / "train_test_metrics.json", "w") as f:
        json.dump(train_test_metrics, f, indent=2)

    # 2. Walk-Forward Validation
    print("Running Walk-Forward Validation...")
    wf_results = []
    for window in config["audit"]["walk_forward"]["windows"]:
        # Filter data by string dates
        # Note: resample_ohlcv already produced datetimes
        test_start = datetime.strptime(window["test"][0], "%Y-%m-%d")
        test_end = datetime.strptime(window["test"][1], "%Y-%m-%d")
        
        df_window = df_4h.filter(pl.col("timestamp").is_between(test_start, test_end))
        if df_window.is_empty(): continue
        
        res_wf = run_backtest(df_window, params, "neutral-exit", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
        wf_results.append({
            "window": window["test"],
            "metrics": res_wf.metrics
        })
    
    with open(artifact_dir / "walk_forward_metrics.json", "w") as f:
        json.dump(wf_results, f, indent=2)

    # 3. Parameter Sensitivity
    print("Running Parameter Sensitivity Grid...")
    ps_cfg = config["audit"]["parameter_sensitivity"]
    sensitivity_results = []
    for period in ps_cfg["rsi_period"]:
        for pair in ps_cfg["threshold_pairs"]:
            for exit_lvl in ps_cfg["exit_levels"]:
                p_sens = RSIMomentumParams(
                    rsi_period=period,
                    rsi_upper=pair["upper"],
                    rsi_lower=pair["lower"],
                    rsi_exit=exit_lvl
                )
                # Run on OOS data (test split)
                res_sens = run_backtest(df_test, p_sens, "neutral-exit", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
                sensitivity_results.append({
                    "params": p_sens.model_dump(),
                    "metrics": res_sens.metrics
                })
    
    with open(artifact_dir / "parameter_sensitivity.json", "w") as f:
        json.dump(sensitivity_results, f, indent=2)

    # 4. Cost Sensitivity
    print("Running Cost Sensitivity...")
    cost_results = []
    for comb in config["audit"]["cost_sensitivity"]["combinations"]:
        res_cost = run_backtest(df_test, params, "neutral-exit", comb["fee"], comb["slippage"])
        cost_results.append({
            "costs": comb,
            "metrics": res_cost.metrics
        })
    
    with open(artifact_dir / "cost_sensitivity.json", "w") as f:
        json.dump(cost_results, f, indent=2)

    # 5. Long/Short Attribution
    print("Running Long/Short Attribution...")
    res_full = run_backtest(df_4h, params, "neutral-exit", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    df_attr = res_full.frame.with_columns(
        long_return = pl.when(pl.col("position") > 0).then(pl.col("net_return")).otherwise(0),
        short_return = pl.when(pl.col("position") < 0).then(pl.col("net_return")).otherwise(0)
    )
    attribution = {
        "long_contribution": float(df_attr.select(pl.col("long_return").sum()).item()),
        "short_contribution": float(df_attr.select(pl.col("short_return").sum()).item()),
        "total_net": float(df_attr.select(pl.col("net_return").sum()).item())
    }
    with open(artifact_dir / "long_short_attribution.json", "w") as f:
        json.dump(attribution, f, indent=2)

    # 6. Trade Distribution & Variant Comparison
    print("Running Variant Comparison & Trade Diagnostics...")
    # Long-flat variant
    res_lf = run_backtest(df_4h, params, "long-flat", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    # Buy and Hold
    res_bh = run_backtest(df_4h, params, "buy-and-hold", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    
    trade_dist = calculate_trade_distribution(res_full.frame)
    with open(artifact_dir / "trade_distribution.json", "w") as f:
        json.dump(trade_dist, f, indent=2)

    fixed_rule_summary = {
        "neutral_exit": res_full.metrics,
        "long_flat": res_lf.metrics,
        "buy_and_hold": res_bh.metrics
    }
    with open(artifact_dir / "fixed_rule_summary.json", "w") as f:
        json.dump(fixed_rule_summary, f, indent=2)

    # 7. Robustness Score
    print("Calculating Robustness Score...")
    score = 0
    reasons = []
    
    # +1 if OOS Sharpe > buy-and-hold (on same test set)
    # We need BH on test set
    res_bh_test = run_backtest(df_test, params, "buy-and-hold", bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    if res_test.metrics.get("smart_sharpe", 0) > res_bh_test.metrics.get("smart_sharpe", 0):
        score += 1
        reasons.append("OOS Sharpe > Buy & Hold Sharpe")
    
    if res_test.metrics.get("max_drawdown", 0) > res_bh_test.metrics.get("max_drawdown", -1): # Max DD is negative
        score += 1
        reasons.append("OOS Max Drawdown < Buy & Hold Max Drawdown")
        
    if res_test.metrics.get("cumulative_return", 0) > 0:
        score += 1
        reasons.append("OOS Return is positive")
        
    prof_windows = [w for w in wf_results if w["metrics"]["cumulative_return"] > 0]
    if len(prof_windows) >= 0.5 * len(wf_results):
        score += 1
        reasons.append(f"{len(prof_windows)}/{len(wf_results)} profitable OOS windows")
        
    # Check sensitivity neighborhood
    prof_sens = [s for s in sensitivity_results if s["metrics"]["cumulative_return"] > 0]
    if len(prof_sens) >= 0.7 * len(sensitivity_results):
        score += 1
        reasons.append("Parameter sensitivity has broad positive neighborhood")

    # Cost sensitivity at 10/5
    cost_10_5 = next((c for c in cost_results if c["costs"]["fee"] == 10 and c["costs"]["slippage"] == 5), None)
    if cost_10_5 and cost_10_5["metrics"]["cumulative_return"] > 0:
        score += 1
        reasons.append("Positive at 10bps fee / 5bps slippage")

    classification = "rejected"
    if score >= 5: classification = "robust"
    elif score >= 3: classification = "promising_but_needs_filters"
    
    robustness_score = {
        "score": score,
        "classification": classification,
        "reasons": reasons
    }
    with open(artifact_dir / "robustness_score.json", "w") as f:
        json.dump(robustness_score, f, indent=2)

    # 8. Report.md
    report_md = f"""# RSI Momentum Robustness Audit Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary
Classification: **{classification.upper()}** (Score: {score}/7)

## Train/Test Metrics
| Period | Return | Sharpe | Max DD |
|--------|--------|--------|--------|
| Train  | {res_train.metrics['cumulative_return']:.2%} | {res_train.metrics['smart_sharpe']:.2f} | {res_train.metrics['max_drawdown']:.2%} |
| Test   | {res_test.metrics['cumulative_return']:.2%} | {res_test.metrics['smart_sharpe']:.2f} | {res_test.metrics['max_drawdown']:.2%} |

## Walk-Forward Results
"""
    for w in wf_results:
        report_md += f"- {w['window'][0]} to {w['window'][1]}: {w['metrics']['cumulative_return']:.2%} return, {w['metrics']['smart_sharpe']:.2f} Sharpe\n"

    report_md += f"""
## Long/Short Attribution
- Long Contribution: {attribution['long_contribution']:.2%}
- Short Contribution: {attribution['short_contribution']:.2%}

## Conclusion
{classification.replace('_', ' ').capitalize()}. {', '.join(reasons)}.
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Audit complete. Artifacts in {artifact_dir}")

if __name__ == "__main__":
    run_robustness_audit()
