"""Tests for RSI Momentum strategy."""

from __future__ import annotations

import unittest

import polars as pl

from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.strategies import available_strategies, get_strategy


def _frame() -> pl.DataFrame:
    """Sample price data for signal testing."""
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 0, 0, 0),
        end=pl.datetime(2024, 1, 3, 0, 0, 0),
        interval="1h",
        eager=True,
    )
    # Create a price series with RSI extreme moves
    prices = [40000, 42000, 44000, 38000, 36000, 35000, 37000, 39000, 41000, 42000,
              44000, 46000, 44000, 42000, 41000, 40000, 38000, 39000, 40000, 41000,
              42000, 44000, 46000, 48000, 50000, 52000, 54000, 52000, 50000, 49000,
              48000, 47000, 46000, 44000, 43000, 42000, 41000, 40000, 39000, 38000,
              37000, 36000, 35000, 34000, 35000, 36000, 37000, 38000, 39000, 40000,
              41000, 42000, 43000, 44000, 45000, 46000, 47000, 48000, 49000, 50000]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices[:len(timestamps)],
            "high": [p + 200 for p in prices[:len(timestamps)]],
            "low": [p - 200 for p in prices[:len(timestamps)]],
            "close": prices[:len(timestamps)],
            "volume": [1000.0] * len(timestamps),
        }
    )


class RSIMomentumTests(unittest.TestCase):
    """Test suite for RSI Momentum strategy."""

    def test_registry_entry(self) -> None:
        """Strategy is registered and accessible."""
        self.assertIn("rsi_momentum", available_strategies())
        module = get_strategy("rsi_momentum")
        self.assertEqual(module.spec.name, "rsi_momentum")

    def test_default_params(self) -> None:
        """Default parameters are sensible."""
        params = get_strategy("rsi_momentum").validate_params({})
        self.assertEqual(params.rsi_period, 14)
        self.assertEqual(params.rsi_upper, 70.0)
        self.assertEqual(params.rsi_lower, 30.0)
        self.assertEqual(params.rsi_exit, 50.0)

    def test_param_types(self) -> None:
        """Parameter types are correctly enforced."""
        params = get_strategy("rsi_momentum").validate_params({
            "rsi_period": 21,
            "rsi_upper": 75.0,
            "rsi_lower": 25.0,
            "rsi_exit": 55.0,
        })
        self.assertEqual(params.rsi_period, 21)
        self.assertEqual(params.rsi_upper, 75.0)
        self.assertEqual(params.rsi_lower, 25.0)
        self.assertEqual(params.rsi_exit, 55.0)

    def test_signal_generation(self) -> None:
        """Signals are generated correctly."""
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({
            "rsi_period": 14,
            "rsi_upper": 70.0,
            "rsi_lower": 30.0,
            "rsi_exit": 50.0,
        })
        df = _frame()
        result = strategy.build_signals(df, params, variant="neutral-exit")

        # Has required columns
        self.assertIn("signal", result.columns)
        self.assertIn("rsi", result.columns)

        # Signal values are valid (-1, 0, 1)
        signals = result["signal"].to_list()
        self.assertTrue(all(s in [-1, 0, 1, None] for s in signals))

    def test_variant_neutral_exit(self) -> None:
        """Neutral-exit variant works correctly."""
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({})
        df = _frame()

        result = strategy.build_signals(df, params, variant="neutral-exit")
        self.assertIn("signal", result.columns)

    def test_variant_extreme_zone(self) -> None:
        """Extreme-zone variant works correctly."""
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({})
        df = _frame()

        result = strategy.build_signals(df, params, variant="extreme-zone")
        self.assertIn("signal", result.columns)

    def test_variant_always_in(self) -> None:
        """Always-in variant works correctly."""
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({})
        df = _frame()

        result = strategy.build_signals(df, params, variant="always-in")
        self.assertIn("signal", result.columns)

    def test_variant_buy_and_hold(self) -> None:
        """Buy-and-hold variant returns all-ones signal."""
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({})
        df = _frame()

        result = strategy.build_signals(df, params, variant="buy-and-hold")
        signals = result["signal"].to_list()
        # All signals should be 1 (long)
        self.assertTrue(all(s == 1 for s in signals if s is not None))

    def test_backtest_runs(self) -> None:
        """Backtest runs without error."""
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({})
        df = _frame()

        signals = strategy.build_signals(df, params, variant="neutral-exit")
        cost_model = CostModel(fee_rate=0.001, slippage_rate=0.0)
        result = PolarsSignalBacktester(initial_capital=10000.0, cost_model=cost_model).run(signals)

        self.assertIsNotNone(result.metrics)
        self.assertIn("cumulative_return", result.metrics)
        self.assertIn("smart_sharpe", result.metrics)
        self.assertIn("max_drawdown", result.metrics)

    def test_eth_outperforms_buy_and_hold(self) -> None:
        """ETH: RSI momentum should outperform buy-and-hold.

        This is a key robustness test - the strategy should demonstrate
        alpha on ETH (2018-2024 period).
        """
        # This test requires the prepared ETH data file
        import os
        eth_data_path = "_artifacts/eth_4h.parquet"
        if not os.path.exists(eth_data_path):
            self.skipTest(f"ETH data not available at {eth_data_path}")

        from quant_stack.data import load_ohlcv_parquet

        df = load_ohlcv_parquet(eth_data_path)
        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({
            "rsi_period": 14,
            "rsi_upper": 70.0,
            "rsi_lower": 30.0,
            "rsi_exit": 50.0,
        })
        cost_model = CostModel(fee_rate=0.001, slippage_rate=0.0)

        # RSI strategy
        signals = strategy.build_signals(df, params, variant="neutral-exit")
        result = PolarsSignalBacktester(initial_capital=10000.0, cost_model=cost_model).run(signals)
        rsi_return = result.metrics.get("cumulative_return", 0)

        # Buy-and-hold
        bh_signals = strategy.build_signals(df, params, variant="buy-and-hold")
        bh_result = PolarsSignalBacktester(initial_capital=10000.0, cost_model=cost_model).run(bh_signals)
        bh_return = bh_result.metrics.get("cumulative_return", 0)

        # RSI should outperform B&H on ETH
        self.assertGreater(rsi_return, bh_return,
                          f"RSI ({rsi_return:.2f}) should outperform B&H ({bh_return:.2f}) on ETH")

    def test_oos_robustness(self) -> None:
        """Out-of-sample validation: 2018-2019 train, 2020-2024 test."""
        import os
        btc_data_path = "_artifacts/btc_4h_2018_2024.parquet"
        if not os.path.exists(btc_data_path):
            self.skipTest(f"BTC data not available at {btc_data_path}")

        from quant_stack.data import load_ohlcv_parquet

        df = load_ohlcv_parquet(btc_data_path)
        df = df.with_columns(pl.col("timestamp").dt.year().alias("year"))

        strategy = get_strategy("rsi_momentum")
        params = strategy.validate_params({
            "rsi_period": 14,
            "rsi_upper": 70.0,
            "rsi_lower": 30.0,
            "rsi_exit": 50.0,
        })
        cost_model = CostModel(fee_rate=0.001, slippage_rate=0.0)

        # Train: 2018-2019
        train_df = df.filter(pl.col("year") < 2020).drop("year")
        train_signals = strategy.build_signals(train_df, params, variant="neutral-exit")
        train_result = PolarsSignalBacktester(initial_capital=10000.0, cost_model=cost_model).run(train_signals)
        train_sharpe = train_result.metrics.get("smart_sharpe", 0)

        # Test: 2020-2024
        test_df = df.filter(pl.col("year") >= 2020).drop("year")
        test_signals = strategy.build_signals(test_df, params, variant="neutral-exit")
        test_result = PolarsSignalBacktester(initial_capital=10000.0, cost_model=cost_model).run(test_signals)
        test_sharpe = test_result.metrics.get("smart_sharpe", 0)

        # Sharpe gap should be reasonable (< 0.5)
        sharpe_gap = abs(train_sharpe - test_sharpe)
        self.assertLess(sharpe_gap, 0.5,
                       f"Sharpe gap {sharpe_gap:.2f} too large - possible overfitting")


if __name__ == "__main__":
    unittest.main()