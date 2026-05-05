import pytest
import polars as pl
import numpy as np
from quant_stack.strategies.rsi_momentum.params import RSIMomentumParams
from quant_stack.strategies.rsi_momentum.signals import build_signals
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.backtesting.costs import CostModel

@pytest.fixture
def sample_data():
    # Synthetic RSI sequence
    # RSI: 40, 45, 55, 75, 60, 45, 40, 25, 35, 55, 60
    return pl.DataFrame({
        "timestamp": [i for i in range(11)],
        "close": [100.0] * 11, 
        "rsi": [40.0, 45.0, 55.0, 75.0, 60.0, 45.0, 40.0, 25.0, 35.0, 55.0, 60.0]
    })

def test_rsi_momentum_neutral_exit_signals(sample_data):
    params = RSIMomentumParams(rsi_upper=70, rsi_lower=30, rsi_exit=50)
    
    # Mock build_features
    from quant_stack.strategies.rsi_momentum import signals
    original_build_features = signals.build_features
    signals.build_features = lambda df, p: df 
    
    try:
        df_signals = build_signals(sample_data, params, variant="neutral-exit")
        expected_signals = [0, 0, 0, 1, 1, 0, 0, -1, -1, 0, 0]
        assert df_signals["signal"].to_list() == expected_signals
    finally:
        signals.build_features = original_build_features

def test_rsi_momentum_extreme_zone_signals(sample_data):
    params = RSIMomentumParams(rsi_upper=70, rsi_lower=30)
    
    from quant_stack.strategies.rsi_momentum import signals
    original_build_features = signals.build_features
    signals.build_features = lambda df, p: df
    
    try:
        df_signals = build_signals(sample_data, params, variant="extreme-zone")
        expected_signals = [0, 0, 0, 1, 0, 0, 0, -1, 0, 0, 0]
        assert df_signals["signal"].to_list() == expected_signals
    finally:
        signals.build_features = original_build_features

def test_backtest_execution_lag():
    # Verify PolarsSignalBacktester uses one-bar lag correctly for research
    df = pl.DataFrame({
        "timestamp": [1, 2, 3, 4],
        "close": [100.0, 110.0, 100.0, 110.0], 
        "signal": [1, 0, 0, 0] 
    })
    
    backtester = PolarsSignalBacktester(cost_model=CostModel(fee_rate=0.0, slippage_rate=0.0))
    res = backtester.run(df)
    
    # Signal at t=1 -> Pos at t=2. Asset Return at t=2 is 10%. Equity at t=2 is 1.1.
    assert res.frame["position"].to_list() == [0.0, 1.0, 0.0, 0.0]
    assert res.frame["equity"].to_list()[1] == pytest.approx(1.1)
