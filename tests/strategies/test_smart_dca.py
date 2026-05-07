"""Tests for Smart DCA strategy."""

from __future__ import annotations

import numpy as np
import polars as pl

from quant_stack.strategies.smart_dca import SmartDCAParams, run_smart_dca_backtest
from quant_stack.strategies.smart_dca.params import EngineConfig


def test_smart_dca_smoke():
    """Test 1: Smoke test with small synthetic DF and only SB enabled."""
    n = 100
    df = pl.DataFrame({
        "timestamp": np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]"),
        "bid": np.linspace(2000, 2010, n),
        "ask": np.linspace(2000.5, 2010.5, n),
    })

    cfg = SmartDCAParams(
        use_time_filter=False,
        sb=EngineConfig(name="SB", enabled=True, side=1, base_lot=0.01, min_step=3.0, tp_dist=2.5, max_levels=20, reduce_levels=10, step_factor=1.1)
    )

    res = run_smart_dca_backtest(df, cfg)
    
    assert "equity" in res
    assert "trade_time_idx" in res
    assert len(res["equity"]) == n
    assert len(res["trade_time_idx"]) > 0


def test_smart_dca_determinism():
    """Test 2: Determinism test."""
    n = 200
    df = pl.DataFrame({
        "timestamp": np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]"),
        "bid": 2000 + 10 * np.sin(np.linspace(0, 4 * np.pi, n)),
        "ask": 2000.5 + 10 * np.sin(np.linspace(0, 4 * np.pi, n)),
    })

    cfg = SmartDCAParams(use_time_filter=False)
    
    res1 = run_smart_dca_backtest(df, cfg)
    res2 = run_smart_dca_backtest(df, cfg)

    for k in res1:
        np.testing.assert_array_equal(res1[k], res2[k])


def test_smart_dca_behavior():
    """Test 3: DCA behavior on falling price."""
    n = 60
    # Price falls by 15 over 60 mins.
    bid = np.linspace(2000, 1985, n)
    ask = bid + 0.5
    df = pl.DataFrame({
        "timestamp": np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]"),
        "bid": bid,
        "ask": ask,
    })

    cfg = SmartDCAParams(
        use_time_filter=False,
        cooldown_entry_sec=0,
        cooldown_dca_sec=0,
        sb=EngineConfig(name="SB", enabled=True, side=1, base_lot=0.01, min_step=3.0, tp_dist=100.0, max_levels=5, reduce_levels=10, step_factor=1.0)
    )

    res = run_smart_dca_backtest(df, cfg)
    reasons = res["trade_reason"]
    
    assert len(reasons) >= 3
    assert reasons[0] == 1  # entry
    assert reasons[1] == 2  # dca
    assert reasons[2] == 2  # dca


def test_smart_dca_tp_behavior():
    """Test 4: TP behavior on falling then rising price."""
    n = 100
    # Price falls then rises.
    bid = np.concatenate([np.linspace(2000, 1990, 50), np.linspace(1990, 2010, 50)])
    ask = bid + 0.5
    df = pl.DataFrame({
        "timestamp": np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]"),
        "bid": bid,
        "ask": ask,
    })

    cfg = SmartDCAParams(
        use_time_filter=False,
        cooldown_entry_sec=0,
        cooldown_dca_sec=0,
        use_tp_trailing=False,
        sb=EngineConfig(name="SB", enabled=True, side=1, base_lot=0.01, min_step=3.0, tp_dist=2.0, max_levels=5, reduce_levels=10, step_factor=1.0)
    )

    res = run_smart_dca_backtest(df, cfg)
    reasons = res["trade_reason"]
    actions = res["trade_action"]

    # Should have at least one close action
    assert -1 in actions
    
    # Reason 3 is normal_tp
    assert 3 in reasons


def test_smart_dca_spread_fallback():
    """Test 5: Spread fallback."""
    n = 50
    # Provide only close
    df = pl.DataFrame({
        "timestamp": np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]"),
        "close": np.linspace(2000, 2010, n),
    })

    cfg = SmartDCAParams(use_time_filter=False)
    
    # Without bid/ask columns, should fail if not manually created
    df_prepared = df.with_columns(
        pl.col("close").alias("bid"),
        pl.col("close").alias("ask")
    )
    
    res = run_smart_dca_backtest(df_prepared, cfg)
    assert len(res["equity"]) == n

if __name__ == "__main__":
    test_smart_dca_smoke()
    test_smart_dca_determinism()
    test_smart_dca_behavior()
    test_smart_dca_tp_behavior()
    test_smart_dca_spread_fallback()
    print("All tests passed!")
