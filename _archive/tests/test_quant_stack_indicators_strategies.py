from __future__ import annotations

import math
import unittest

import polars as pl

from quant_stack.indicators.polars import (
    atr,
    bollinger_bands,
    ema,
    log_returns,
    rolling_high,
    rolling_low,
    rolling_volatility,
    rolling_zscore,
    rsi,
    simple_returns,
    sma,
)
from quant_stack.strategies import available_strategies, get_strategy
from quant_stack.strategies.bb_breakout.params import BBBreakoutParams
from quant_stack.strategies.rsi_sma.params import RSISMAParams


def _frame(closes: list[float]) -> pl.DataFrame:
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 0, 0, 0),
        end=pl.datetime(2024, 1, 1, 0, len(closes) - 1, 0),
        interval="1m",
        eager=True,
    )
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": [1.0] * len(closes),
        }
    )


class QuantStackIndicatorTests(unittest.TestCase):
    def test_sma_fixture(self) -> None:
        result = _frame([1, 2, 3, 4]).with_columns(sma(window=3, alias="sma"))

        self.assertEqual(result["sma"].to_list(), [None, None, 2.0, 3.0])

    def test_ema_fixture(self) -> None:
        result = _frame([1, 2, 3, 4]).with_columns(ema(span=3, alias="ema"))

        self.assertEqual(result["ema"].to_list()[:2], [None, None])
        self.assertAlmostEqual(result["ema"].to_list()[2], 2.25)
        self.assertAlmostEqual(result["ema"].to_list()[3], 3.125)

    def test_rolling_high_low_fixtures(self) -> None:
        result = _frame([1, 2, 3, 4]).with_columns(
            [rolling_high(window=2, alias="rolling_high"), rolling_low(window=2, alias="rolling_low")]
        )

        self.assertEqual(result["rolling_high"].to_list(), [None, 2.5, 3.5, 4.5])
        self.assertEqual(result["rolling_low"].to_list(), [None, 0.5, 1.5, 2.5])

    def test_returns_fixtures(self) -> None:
        result = _frame([100.0, 110.0, 121.0]).with_columns(
            [simple_returns(alias="ret"), log_returns(alias="log_ret")]
        )

        self.assertIsNone(result["ret"].to_list()[0])
        self.assertAlmostEqual(result["ret"].to_list()[1], 0.10)
        self.assertAlmostEqual(result["ret"].to_list()[2], 0.10)
        self.assertAlmostEqual(result["log_ret"].to_list()[1], math.log(1.1))

    def test_bollinger_fixture_uses_population_std(self) -> None:
        result = _frame([1.0, 2.0, 3.0]).with_columns(
            bollinger_bands(window=3, num_std=1.0, middle_alias="middle", upper_alias="upper", lower_alias="lower")
        )

        expected_std = math.sqrt(2.0 / 3.0)
        self.assertAlmostEqual(result["middle"].to_list()[-1], 2.0)
        self.assertAlmostEqual(result["upper"].to_list()[-1], 2.0 + expected_std)
        self.assertAlmostEqual(result["lower"].to_list()[-1], 2.0 - expected_std)

    def test_simple_rolling_rsi_fixture(self) -> None:
        result = _frame([1.0, 2.0, 3.0, 2.0]).with_columns(rsi(window=3, alias="rsi"))

        self.assertAlmostEqual(result["rsi"].to_list()[-1], 100.0 * (2.0 / 3.0))

    def test_volatility_zscore_and_atr_fixtures(self) -> None:
        result = _frame([1.0, 2.0, 3.0, 4.0]).with_columns(simple_returns(alias="ret")).with_columns(
            [
                rolling_volatility("ret", window=2, alias="vol"),
                rolling_zscore("close", window=2, alias="zscore"),
                atr(window=2, alias="atr"),
            ]
        )

        self.assertAlmostEqual(result["vol"].to_list()[2], math.sqrt(0.125))
        self.assertAlmostEqual(result["zscore"].to_list()[3], 1.0 / math.sqrt(2.0))
        self.assertEqual(result["atr"].to_list(), [None, 1.25, 1.5, 1.5])


class QuantStackStrategyTests(unittest.TestCase):
    def test_default_registry_contains_new_strategy_modules(self) -> None:
        self.assertEqual(
            available_strategies(),
            [
                "bb_breakout",
                "forced_flow_band_reclaim",
                "funding_exhaustion_reversal",
                "grid",
                "oi_confirmed_trend",
                "rsi_sma",
            ],
        )

        rsi_module = get_strategy("rsi-sma")
        bb_module = get_strategy("bb_breakout")
        grid_module = get_strategy("grid")

        self.assertEqual(rsi_module.spec.default_engine, "polars")
        self.assertEqual(bb_module.spec.timeframe, "1h")
        self.assertEqual(grid_module.spec.signal_mode, "path_dependent")
        self.assertEqual(grid_module.spec.default_engine, "vectorbt")

    def test_rsi_sma_params_validate_window_order(self) -> None:
        module = get_strategy("rsi_sma")

        params = module.validate_params({"short_sma": 2, "long_sma": 3, "rsi_period": 2, "rsi_threshold": 50.0})
        self.assertIsInstance(params, RSISMAParams)
        with self.assertRaises(ValueError):
            module.validate_params({"short_sma": 5, "long_sma": 3, "rsi_period": 2, "rsi_threshold": 50.0})

    def test_rsi_sma_builds_features_and_cross_signals(self) -> None:
        module = get_strategy("rsi_sma")
        params = RSISMAParams(short_sma=2, long_sma=3, rsi_period=2, rsi_threshold=50.0, rsi_side="above")
        result = module.build_signals(_frame([3.0, 2.0, 1.0, 2.0, 4.0]), params)

        self.assertIn("short_sma", result.columns)
        self.assertIn("long_sma", result.columns)
        self.assertIn("rsi", result.columns)
        self.assertTrue(result["entry_signal"].to_list()[-1])
        self.assertEqual(result["signal"].to_list()[-1], 1)

    def test_bb_breakout_builds_features_and_signals(self) -> None:
        module = get_strategy("bb_breakout")
        params = BBBreakoutParams(bb_length=3, bb_std=1.0, regime_sma=3)
        result = module.build_signals(_frame([1.0, 2.0, 3.0, 6.0, 1.0]), params)

        self.assertIn("bb_middle", result.columns)
        self.assertIn("bb_upper", result.columns)
        self.assertIn("regime_sma", result.columns)
        self.assertTrue(result["entry_signal"].to_list()[3])
        self.assertTrue(result["exit_signal"].to_list()[4])

    def test_grid_strategy_is_registered_as_path_dependent_placeholder(self) -> None:
        module = get_strategy("grid")
        params = module.validate_params({"num_levels": 4, "grid_width_pct": 0.2, "fee_pct": 0.001})
        result = module.build_signals(_frame([1.0, 2.0, 3.0]), params)

        self.assertEqual(result["grid_num_levels"].to_list(), [4, 4, 4])
        self.assertEqual(result["signal"].to_list(), [None, None, None])


if __name__ == "__main__":
    unittest.main()
