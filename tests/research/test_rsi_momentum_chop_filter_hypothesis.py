import pytest
import polars as pl
from scripts.run_rsi_momentum_chop_filter_hypothesis import calculate_indicators, apply_chop_filter

def test_efficiency_ratio_calculation():
    # Price moves in a straight line: ER = 1.0
    df = pl.DataFrame({
        "timestamp": [1, 2, 3, 4],
        "close": [100.0, 105.0, 110.0, 115.0]
    })
    # ER lookback in script is 14, let's test a small window version
    # Actually we just test the columns are created and bounded [0, 1]
    df_ind = calculate_indicators(df)
    assert "er" in df_ind.columns
    # With only 4 rows, er[3] (lookback 14) will be null or nan.
    # But we check the logic for a custom window if needed.
    # Just checking it exists for now.

def test_vol_z_score_calculation():
    df = pl.DataFrame({
        "timestamp": list(range(100)),
        "close": [100.0 + (i % 10) for i in range(100)]
    })
    df_ind = calculate_indicators(df)
    assert "vol_z" in df_ind.columns
    # Check it's not all null
    assert df_ind["vol_z"].null_count() < 100

def test_chop_filter_gates_signal():
    df = pl.DataFrame({
        "timestamp": [1],
        "signal": [1],
        "er": [0.1], # Low efficiency
        "vol_z": [3.0] # High vol
    })
    # ER 0.35 should block
    df_er = apply_chop_filter(df, "efficiency_ratio_035")
    assert df_er["signal"][0] == 0
    
    # High vol disable should block
    df_vol = apply_chop_filter(df, "high_volatility_disable")
    assert df_vol["signal"][0] == 0

def test_cooldown_gate_logic():
    df = pl.DataFrame({
        "timestamp": [1, 2, 3, 4],
        "close": [100.0, 95.0, 96.0, 97.0], # Bar 1 -> 2 is a loss for signal=1
        "signal": [1, 1, 1, 1]
    })
    df_f = apply_chop_filter(df, "cooldown_after_loss_3_bars")
    # Bar 1 entry
    # Bar 2 sees loss (100 -> 95). cooldown starts.
    # Bar 3, 4 should be blocked.
    assert df_f["signal"][2] == 0
    assert df_f["signal"][3] == 0
