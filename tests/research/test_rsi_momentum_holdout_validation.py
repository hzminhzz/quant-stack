import pytest
import polars as pl
from scripts.run_rsi_momentum_holdout_validation import apply_high_vol_disable

def test_high_vol_disable_logic():
    # Create data with stable vol then high vol spike
    # 42 bars of 1.0, then 10 bars of alternating 0.5 and 1.5 (high vol)
    closes = [100.0] * 50 + [100.0, 110.0, 90.0, 110.0, 90.0] * 5
    df = pl.DataFrame({
        "timestamp": list(range(len(closes))),
        "close": closes,
        "signal": [1] * len(closes)
    })
    
    df_f = apply_high_vol_disable(df, threshold=1.0)
    # The spike at the end should have high vol_z and signal=0
    last_signals = df_f["signal"].tail(10).to_list()
    assert 0 in last_signals
    # Initial signals should be 1 (or 0 if vol_std=0 but Polars handles it)
    assert df_f["signal"][45] == 1

def test_holdout_query_parses():
    from pathlib import Path
    import yaml
    query_path = Path("examples/pipeline_queries/rsi_momentum_holdout_validation.yaml")
    assert query_path.exists()
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    assert "holdout_symbols" in config
    assert "SOL-USDT" in config["holdout_symbols"]
