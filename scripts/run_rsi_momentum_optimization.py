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

def load_data():
    data_files = sorted(Path("Data/Binance").glob("BTC_1m_*.parquet"))
    dfs = [pl.read_parquet(f) for f in data_files]
    raw_df = pl.concat(dfs).sort("timestamp")
    df_dt = raw_df.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("timestamp"))
    return resample_ohlcv(df_dt, every="4h")

def run_bt(df: pl.DataFrame, params: RSIMomentumParams, fee_bps: float, slippage_bps: float):
    cost_model = CostModel(fee_rate=fee_bps/10000.0, slippage_rate=slippage_bps/10000.0)
    backtester = PolarsSignalBacktester(cost_model=cost_model)
    df_signals = build_signals(df, params, variant="neutral-exit")
    return backtester.run(df_signals)

class ObjectiveScorer:
    @staticmethod
    def calculate_score(metrics: Dict[str, Any], is_metrics: Dict[str, Any] = None) -> float:
        # Deterministic ranking-based score
        sharpe = metrics.get("smart_sharpe", 0)
        ret = metrics.get("cumulative_return", 0)
        mdd = metrics.get("max_drawdown", -1) # DD is negative
        
        # Penalties
        penalty = 0.0
        if ret < 0: penalty += 5.0
        if mdd < -0.25: penalty += 2.0
        
        # Overfit gap penalty
        if is_metrics:
            is_ret = is_metrics.get("cumulative_return", 0)
            if is_ret > ret * 2: # Significant IS/OOS gap
                penalty += 1.0
                
        # Objective function
        # Weighted Sharpe + Return + Calmar - Penalties
        calmar = abs(ret / mdd) if mdd != 0 else 0
        score = (sharpe * 1.0) + (ret * 0.5) + (calmar * 0.2) - penalty
        return float(score)

def run_optimization():
    # 1. Setup
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_extreme_momentum_optimization.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    
    artifact_dir = Path("artifacts/research/btc_4h_rsi_extreme_momentum_optimization_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    df_4h = load_data()
    
    # Splits
    sp = config["splits"]
    n = len(df_4h)
    train_end = int(n * sp["train"])
    val_end = train_end + int(n * sp["validation"])
    
    df_train = df_4h.head(train_end)
    df_val = df_4h.slice(train_end, val_end - train_end)
    df_holdout = df_4h.tail(n - val_end)
    
    print(f"Splits: Train {len(df_train)}, Val {len(df_val)}, Holdout {len(df_holdout)}")
    
    bt_cfg = config["backtest"]
    
    # 2. Champion Baseline
    cp = config["champion_parameters"]
    champ_params = RSIMomentumParams(**cp)
    res_champ_val = run_bt(df_val, champ_params, bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    res_champ_is = run_bt(df_train, champ_params, bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    
    champ_score = ObjectiveScorer.calculate_score(res_champ_val.metrics, res_champ_is.metrics)
    
    with open(artifact_dir / "champion_metrics.json", "w") as f:
        json.dump(res_champ_val.metrics, f, indent=2)

    # 3. Grid Search
    space = config["search_space"]
    cons = config["constraints"]
    
    results = []
    scores = []
    
    configs_tested = 0
    for period in space["rsi_period"]:
        for upper in space["rsi_upper"]:
            for lower in space["rsi_lower"]:
                for exit_lvl in space["rsi_exit"]:
                    # Constraints
                    if upper <= exit_lvl: continue
                    if lower >= exit_lvl: continue
                    if upper - lower < cons["min_range"]: continue
                    
                    configs_tested += 1
                    p = RSIMomentumParams(rsi_period=period, rsi_upper=upper, rsi_lower=lower, rsi_exit=exit_lvl)
                    
                    res_is = run_bt(df_train, p, bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
                    res_val = run_bt(df_val, p, bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
                    
                    score = ObjectiveScorer.calculate_score(res_val.metrics, res_is.metrics)
                    
                    results.append({
                        "params": p.model_dump(),
                        "is_metrics": res_is.metrics,
                        "val_metrics": res_val.metrics,
                        "score": score
                    })
                    scores.append(score)

    print(f"Tested {configs_tested} valid configurations.")
    
    # 4. Selection
    results.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = results[:10]
    best_candidate = results[0]
    
    with open(artifact_dir / "optimization_grid_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    with open(artifact_dir / "top_candidates.json", "w") as f:
        json.dump(top_candidates, f, indent=2)
        
    with open(artifact_dir / "selected_candidate.json", "w") as f:
        json.dump(best_candidate, f, indent=2)

    # 5. Champion vs Challenger
    challenger_params = RSIMomentumParams(**best_candidate["params"])
    
    # Evaluation on Holdout (Final Gate)
    res_champ_ho = run_bt(df_holdout, champ_params, bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    res_chall_ho = run_bt(df_holdout, challenger_params, bt_cfg["fee_bps"], bt_cfg["slippage_bps"])
    
    holdout_metrics = {
        "champion": res_champ_ho.metrics,
        "challenger": res_chall_ho.metrics,
        "timestamps": {
            "train": [str(df_train["timestamp"].min()), str(df_train["timestamp"].max())],
            "val": [str(df_val["timestamp"].min()), str(df_val["timestamp"].max())],
            "holdout": [str(df_holdout["timestamp"].min()), str(df_holdout["timestamp"].max())]
        }
    }
    with open(artifact_dir / "final_holdout_metrics.json", "w") as f:
        json.dump(holdout_metrics, f, indent=2)

    # Promotion logic
    promotion = "keep_champion"
    if best_candidate["score"] > champ_score and res_chall_ho.metrics["smart_sharpe"] > res_champ_ho.metrics["smart_sharpe"]:
        promotion = "promote_challenger"
    
    optimization_result = {
        "promotion": promotion,
        "champion_params": champ_params.model_dump(),
        "challenger_params": best_candidate["params"],
        "num_configs": configs_tested
    }
    with open(artifact_dir / "optimization_result.json", "w") as f:
        json.dump(optimization_result, f, indent=2)

    # 6. Report.md
    report_md = f"""# RSI Momentum Optimization Report (Phase 18B)
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Result: {promotion.upper()}

## Splits
- **Train**: {holdout_metrics['timestamps']['train'][0]} to {holdout_metrics['timestamps']['train'][1]}
- **Validation**: {holdout_metrics['timestamps']['val'][0]} to {holdout_metrics['timestamps']['val'][1]}
- **Holdout**: {holdout_metrics['timestamps']['holdout'][0]} to {holdout_metrics['timestamps']['holdout'][1]}

## Parameters
| Type | RSI Period | Upper | Lower | Exit |
|------|------------|-------|-------|------|
| Champion | {champ_params.rsi_period} | {champ_params.rsi_upper} | {champ_params.rsi_lower} | {champ_params.rsi_exit} |
| Challenger | {challenger_params.rsi_period} | {challenger_params.rsi_upper} | {challenger_params.rsi_lower} | {challenger_params.rsi_exit} |

## Performance (Final Holdout)
| Metric | Champion | Challenger |
|--------|----------|------------|
| Return | {res_champ_ho.metrics['cumulative_return']:.2%} | {res_chall_ho.metrics['cumulative_return']:.2%} |
| Sharpe | {res_champ_ho.metrics['smart_sharpe']:.2f} | {res_chall_ho.metrics['smart_sharpe']:.2f} |
| Max DD | {res_champ_ho.metrics['max_drawdown']:.2%} | {res_chall_ho.metrics['max_drawdown']:.2%} |

## Conclusion
{promotion.replace('_', ' ').capitalize()}. Tested {configs_tested} valid configurations. 
"""
    with open(artifact_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"Optimization complete. Promotion: {promotion}")

if __name__ == "__main__":
    run_optimization()
