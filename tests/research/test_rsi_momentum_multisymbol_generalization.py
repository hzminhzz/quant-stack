import pytest
import polars as pl
from pathlib import Path
import yaml
from scripts.run_rsi_momentum_multisymbol_generalization import load_and_resample, apply_trend_filter

def test_resampling_logic():
    # Mock 1m data: 240 mins (4 hours)
    df_1m = pl.DataFrame({
        "timestamp": pl.datetime_range(datetime(2021,1,1), datetime(2021,1,1,3,59), interval="1m", eager=True),
        "open": [100.0] * 240,
        "high": [110.0] * 240,
        "low": [90.0] * 240,
        "close": [105.0] * 240,
        "volume": [10.0] * 240
    }).with_columns(pl.col("timestamp").dt.epoch("ms"))
    
    # We can't easily mock load_and_resample because it reads files.
    # But we can test resample_ohlcv from quant_stack.data.resample
    from quant_stack.data.resample import resample_ohlcv
    df_dt = df_1m.with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("timestamp"))
    df_4h = resample_ohlcv(df_dt, every="4h")
    
    assert len(df_4h) == 1
    assert df_4h["open"][0] == 100.0
    assert df_4h["high"][0] == 110.0
    assert df_4h["low"][0] == 90.0
    assert df_4h["close"][0] == 105.0
    assert df_4h["volume"][0] == 2400.0

def test_trend_filter_consistency():
    df = pl.DataFrame({
        "timestamp": [1, 2, 3],
        "close": [100.0, 110.0, 120.0],
        "signal": [1, 1, 1]
    })
    # SMA 2 (fast) vs SMA 3 (slow)
    # t=1: SMA2=null, SMA3=null
    # t=2: SMA2=105, SMA3=null
    # t=3: SMA2=115, SMA3=110 -> allowed=1
    params = {"sma_period_fast": 2, "sma_period_slow": 3}
    df_filtered = apply_trend_filter(df, params)
    assert df_filtered["signal"].to_list()[-1] == 1

def test_multisymbol_query_parses():
    query_path = Path("examples/pipeline_queries/rsi_momentum_trend_filter_multisymbol.yaml")
    assert query_path.exists()
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    assert "symbols" in config
    assert len(config["symbols"]) >= 2
from datetime import datetime
