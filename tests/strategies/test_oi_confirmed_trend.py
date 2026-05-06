from __future__ import annotations

import unittest

import polars as pl

from quant_stack.strategies import available_strategies, get_strategy
from quant_stack.strategies.oi_confirmed_trend.params import OIConfirmedTrendParams


def _frame() -> pl.DataFrame:
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 0, 0, 0),
        end=pl.datetime(2024, 1, 1, 0, 4, 0),
        interval="1m",
        eager=True,
    )
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "close": [100.0, 101.0, 102.0, 101.0, 99.0],
            "ema_20": [99.0, 100.0, 101.0, 101.0, 100.0],
            "ema_dist_20": [0.01, 0.01, 0.01, 0.00, -0.01],
            "trend_strength_50_200": [0.1, 0.2, 0.3, 0.1, -0.1],
            "oi_zscore_60": [0.2, 1.2, 1.4, 0.8, -0.2],
            "oi_change_pct_5": [0.0, 0.1, 0.2, 0.0, -0.1],
            "funding_zscore_30": [0.5, 0.7, 0.6, 2.0, 0.1],
            "basis_zscore_60": [0.4, 0.6, 0.7, 2.0, 0.1],
            "spread_bps": [2.0, 2.0, 2.0, 2.0, 2.0],
        }
    )


class OIConfirmedTrendTests(unittest.TestCase):
    def test_module_imports_and_registry_entry(self) -> None:
        self.assertIn("oi_confirmed_trend", available_strategies())
        module = get_strategy("oi_confirmed_trend")
        self.assertEqual(module.spec.default_engine, "polars")
        self.assertEqual(module.spec.signal_mode, "vectorized")

    def test_params_validate(self) -> None:
        params = OIConfirmedTrendParams(max_spread_bps=3.0)
        self.assertEqual(params.max_spread_bps, 3.0)
        with self.assertRaises(ValueError):
            OIConfirmedTrendParams(max_spread_bps=-1.0)

    def test_baseline_bullish_trend_creates_entry_without_context(self) -> None:
        module = get_strategy("oi_confirmed_trend")
        params = OIConfirmedTrendParams(use_context_filters=False)
        result = module.build_signals(_frame().drop("oi_zscore_60", "oi_change_pct_5", "funding_zscore_30", "basis_zscore_60"), params)

        self.assertEqual(result.height, _frame().height)
        self.assertEqual(result["timestamp"].to_list(), _frame().sort("timestamp")["timestamp"].to_list())
        self.assertTrue(result["entry_signal"].to_list()[1])
        self.assertTrue(all(value in (0, 1, None) for value in result["signal"].to_list()))

    def test_oi_expansion_confirms_entry_in_context_mode(self) -> None:
        module = get_strategy("oi_confirmed_trend")
        params = OIConfirmedTrendParams()
        result = module.build_signals(_frame(), params)
        self.assertTrue(result["entry_signal"].to_list()[1])

    def test_funding_crowded_filter_blocks_entry(self) -> None:
        module = get_strategy("oi_confirmed_trend")
        params = OIConfirmedTrendParams(funding_crowded_threshold=0.0)
        result = module.build_signals(_frame(), params)
        self.assertFalse(any(result["entry_signal"].to_list()))

    def test_basis_crowded_filter_blocks_entry(self) -> None:
        module = get_strategy("oi_confirmed_trend")
        params = OIConfirmedTrendParams(basis_crowded_threshold=0.0)
        result = module.build_signals(_frame(), params)
        self.assertFalse(any(result["entry_signal"].to_list()))

    def test_trend_reversal_exit_works(self) -> None:
        module = get_strategy("oi_confirmed_trend")
        params = OIConfirmedTrendParams()
        result = module.build_signals(_frame(), params)
        self.assertTrue(result["exit_signal"].to_list()[4])

    def test_context_mode_missing_columns_raises(self) -> None:
        module = get_strategy("oi_confirmed_trend")
        params = OIConfirmedTrendParams(use_context_filters=True, require_oi_expansion=True)
        with self.assertRaises(ValueError):
            module.build_signals(_frame().drop("oi_zscore_60", "oi_change_pct_5"), params)

    def test_no_forbidden_imports(self) -> None:
        content = open("quant_stack/strategies/oi_confirmed_trend/signals.py", encoding="utf-8").read()
        forbidden = ["pandas", "ccxt", "pybit", "requests", "quant_stack.live", "quant_stack.execution", "quant_stack.backtesting", "strategy_families", "engine.backtester"]
        for token in forbidden:
            self.assertNotIn(token, content)


class RegistryCoverageTests(unittest.TestCase):
    def test_registry_includes_phase_18e_strategies(self) -> None:
        names = available_strategies()
        self.assertIn("forced_flow_band_reclaim", names)
        self.assertIn("funding_exhaustion_reversal", names)
        self.assertIn("oi_confirmed_trend", names)

    def test_get_strategy_specs(self) -> None:
        for name in ["forced_flow_band_reclaim", "funding_exhaustion_reversal", "oi_confirmed_trend"]:
            module = get_strategy(name)
            self.assertEqual(module.spec.default_engine, "polars")
            self.assertEqual(module.spec.signal_mode, "vectorized")


if __name__ == "__main__":
    unittest.main()
