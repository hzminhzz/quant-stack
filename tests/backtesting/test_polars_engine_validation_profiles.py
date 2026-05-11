from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from quant_stack.backtesting.costs import CostModel
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester


def _market_frame(close: list[float], signal: list[float]) -> pl.DataFrame:
    start = datetime(2026, 1, 1, 0, 0, 0)
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=i) for i in range(len(close))],
            "close": close,
            "signal": signal,
        }
    )


def test_no_lookahead_signal_lag_position_shift() -> None:
    frame = _market_frame(
        close=[100.0, 101.0, 102.0, 103.0],
        signal=[0.0, 1.0, 1.0, 0.0],
    )
    result = PolarsSignalBacktester(initial_capital=10000.0).run(frame)
    assert result.frame["target_position"].to_list() == [0.0, 1.0, 1.0, 0.0]
    assert result.frame["position"].to_list() == [0.0, 0.0, 1.0, 1.0]


def test_turnover_matches_absolute_position_change() -> None:
    frame = _market_frame(
        close=[100.0, 101.0, 102.0, 103.0, 104.0],
        signal=[0.0, 1.0, 0.0, 1.0, 0.0],
    )
    result = PolarsSignalBacktester(initial_capital=10000.0).run(frame)
    expected = [0.0, 0.0, 1.0, 1.0, 1.0]
    assert result.frame["turnover"].to_list() == expected


def test_cost_profile_reduces_final_equity_vs_no_costs() -> None:
    frame = _market_frame(
        close=[100.0, 102.0, 101.0, 104.0, 103.0, 105.0],
        signal=[0.0, 1.0, 1.0, 0.0, 1.0, 0.0],
    )
    base = PolarsSignalBacktester(initial_capital=10000.0, cost_model=CostModel(fee_rate=0.0, slippage_rate=0.0)).run(frame)
    costly = PolarsSignalBacktester(initial_capital=10000.0, cost_model=CostModel(fee_rate=0.001, slippage_rate=0.001)).run(frame)
    assert costly.frame["equity"].to_list()[-1] < base.frame["equity"].to_list()[-1]


def test_equity_path_matches_cumprod_definition() -> None:
    frame = _market_frame(
        close=[100.0, 101.0, 103.0, 102.0, 104.0],
        signal=[0.0, 1.0, 1.0, 1.0, 0.0],
    )
    initial = 5000.0
    result = PolarsSignalBacktester(initial_capital=initial, cost_model=CostModel(fee_rate=0.0, slippage_rate=0.0)).run(frame)
    recomputed = (
        result.frame.select(((1.0 + pl.col("net_return")).cum_prod() * initial).alias("expected_equity"))["expected_equity"].to_list()
    )
    assert result.frame["equity"].to_list() == recomputed


def test_exposure_is_bounded_and_binary_for_polars_profile() -> None:
    frame = _market_frame(
        close=[100.0, 99.0, 101.0, 103.0, 102.0, 100.0],
        signal=[0.0, 0.2, 0.8, 1.0, 0.4, 0.0],
    )
    result = PolarsSignalBacktester(initial_capital=10000.0).run(frame)
    positions = result.frame["position"].to_list()
    assert all(0.0 <= p <= 1.0 for p in positions)
    exposures = result.frame["is_exposed"].to_list()
    assert all(isinstance(x, bool) for x in exposures)


def test_constant_price_no_cost_profile_keeps_equity_constant() -> None:
    frame = _market_frame(
        close=[100.0, 100.0, 100.0, 100.0, 100.0],
        signal=[0.0, 1.0, 1.0, 0.0, 0.0],
    )
    result = PolarsSignalBacktester(
        initial_capital=2500.0,
        cost_model=CostModel(fee_rate=0.0, slippage_rate=0.0),
    ).run(frame)
    assert result.frame["equity"].to_list() == [2500.0, 2500.0, 2500.0, 2500.0, 2500.0]


def test_exact_cost_accounting_matches_turnover_times_rate() -> None:
    frame = _market_frame(
        close=[100.0, 100.0, 100.0, 100.0, 100.0],
        signal=[0.0, 1.0, 1.0, 0.0, 0.0],
    )
    fee_rate = 0.002
    result = PolarsSignalBacktester(
        initial_capital=1000.0,
        cost_model=CostModel(fee_rate=fee_rate, slippage_rate=0.0),
    ).run(frame)
    out = result.frame
    expected_cost = out.select((pl.col("turnover") * fee_rate).alias("expected_cost"))["expected_cost"].to_list()
    assert out["cost_return"].to_list() == expected_cost


def test_adversarial_signal_does_not_capture_same_bar_jump() -> None:
    frame = _market_frame(
        close=[100.0, 100.0, 100.0, 200.0, 200.0],
        signal=[0.0, 0.0, 0.0, 1.0, 1.0],
    )
    result = PolarsSignalBacktester(
        initial_capital=1000.0,
        cost_model=CostModel(fee_rate=0.0, slippage_rate=0.0),
    ).run(frame)
    out = result.frame
    jump_idx = 3
    assert out["asset_return"][jump_idx] == 1.0
    assert out["position"][jump_idx] == 0.0
    assert out["gross_return"][jump_idx] == 0.0
