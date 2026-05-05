import pytest
import polars as pl
import yaml
from pathlib import Path
from scripts.run_rsi_momentum_robustness import run_backtest
from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams

def test_robustness_query_parses():
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_extreme_momentum_robustness.yaml")
    assert query_path.exists()
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    assert "audit" in config
    assert "parameter_sensitivity" in config["audit"]

def test_parameter_grid_size():
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_extreme_momentum_robustness.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    ps = config["audit"]["parameter_sensitivity"]
    total = len(ps["rsi_period"]) * len(ps["threshold_pairs"]) * len(ps["exit_levels"])
    assert total == 27

def test_long_flat_variant_no_shorts():
    # Mock data
    df = pl.DataFrame({
        "timestamp": [1, 2, 3],
        "close": [100.0, 100.0, 100.0],
        "rsi": [80.0, 20.0, 80.0]
    })
    params = RSIMomentumParams(rsi_upper=70, rsi_lower=30, rsi_exit=50)
    
    from quant_stack.strategies.rsi_momentum import signals
    orig_bf = signals.build_features
    signals.build_features = lambda d, p: d
    
    try:
        res = run_backtest(df, params, "long-flat", 0, 0)
        # Check positions
        # RSI 80 -> 1
        # RSI 20 -> should stay 1? No, long-flat: if < 50, flat.
        # RSI 20 < 50 -> 0.
        # RSI 80 -> 1.
        # Signals: [1, 0, 1]
        # Backtest (1-bar lag): [0, 1, 0]
        assert all(p >= 0 for p in res.frame["position"].to_list())
    finally:
        signals.build_features = orig_bf

def test_walk_forward_windows_logical():
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_extreme_momentum_robustness.yaml")
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    windows = config["audit"]["walk_forward"]["windows"]
    for w in windows:
        train_end = w["train"][1]
        test_start = w["test"][0]
        assert train_end < test_start or train_end == test_start # Depends on bounds
