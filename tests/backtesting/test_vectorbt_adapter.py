"""Tests for the vectorbt adapter."""

import polars as pl
import pytest
from numpy.testing import assert_almost_equal

from quant_stack.backtesting.costs import CostModel
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.backtesting.vectorbt_engine import VectorBTBacktester

try:
    import vectorbt  # noqa
    HAS_VBT = True
except ImportError:
    HAS_VBT = False

pytestmark = pytest.mark.skipif(not HAS_VBT, reason="vectorbt not installed")


@pytest.fixture
def sample_data() -> pl.DataFrame:
    # 10 days of synthetic data
    return pl.DataFrame(
        {
            "timestamp": pl.date_range(pl.datetime(2025, 1, 1), pl.datetime(2025, 1, 10), "1d", eager=True),
            "close": [100.0, 105.0, 110.0, 108.0, 115.0, 120.0, 118.0, 125.0, 130.0, 128.0],
            "signal": [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0],
        }
    )


def test_vectorbt_matches_polars_long_only(sample_data: pl.DataFrame) -> None:
    cost_model = CostModel(fee_rate=0.001, slippage_rate=0.0)
    
    polars_engine = PolarsSignalBacktester(initial_capital=1000.0, cost_model=cost_model)
    vbt_engine = VectorBTBacktester(initial_capital=1000.0, cost_model=cost_model)
    
    res_polars = polars_engine.run(sample_data)
    res_vbt = vbt_engine.run(sample_data)
    
    # Total returns should match very closely
    assert_almost_equal(res_polars.metrics["cumulative_return"], res_vbt.metrics["cumulative_return"], decimal=3)
    
    # Equity curves should match closely
    eq_polars = res_polars.frame["equity"].to_list()
    eq_vbt = res_vbt.frame["equity"].to_list()
    
    for ep, ev in zip(eq_polars, eq_vbt):
        assert_almost_equal(ep, ev, decimal=3)


def test_vectorbt_sl_stop() -> None:
    df = pl.DataFrame(
        {
            "timestamp": pl.date_range(pl.datetime(2025, 1, 1), pl.datetime(2025, 1, 5), "1d", eager=True),
            "close": [100.0, 100.0, 90.0, 80.0, 100.0],
            "signal": [0.0, 1.0, 1.0, 1.0, 1.0], 
        }
    )
    vbt_engine_no_sl = VectorBTBacktester(initial_capital=1000.0, cost_model=CostModel())
    res_no_sl = vbt_engine_no_sl.run(df)
    
    vbt_engine_sl = VectorBTBacktester(initial_capital=1000.0, cost_model=CostModel(), sl_stop=0.05)
    res_sl = vbt_engine_sl.run(df)
    
    # SL should limit the max drawdown compared to no SL
    assert res_sl.metrics["max_drawdown"] < res_no_sl.metrics["max_drawdown"]
    
    # We should have 1 trade exited by SL
    assert len(res_sl.trades) == 1
    assert res_sl.trades[0] <= -0.04 # roughly -5%
