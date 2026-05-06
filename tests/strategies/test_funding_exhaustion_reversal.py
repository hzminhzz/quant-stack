from __future__ import annotations

import unittest

import polars as pl

from quant_stack.strategies import available_strategies, get_strategy
from quant_stack.strategies.funding_exhaustion_reversal.params import FundingExhaustionReversalParams


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
            "rsi_14": [45.0, 25.0, 28.0, 52.0, 60.0],
            "funding_zscore_30": [-0.5, -2.6, -2.3, -0.2, 0.3],
            "momentum_slope_10": [-0.1, 0.2, 0.3, 0.1, -0.2],
            "price_extension_20": [-0.01, -0.04, -0.03, 0.01, 0.02],
            "ret_60": [-0.01, -0.05, -0.03, 0.00, 0.01],
            "basis_zscore_60": [-0.2, -1.9, -1.7, -0.2, 0.4],
            "spread_bps": [2.0, 2.0, 2.0, 2.0, 2.0],
        }
    )


class FundingExhaustionReversalTests(unittest.TestCase):
    def test_module_imports_and_registry_entry(self) -> None:
        self.assertIn("funding_exhaustion_reversal", available_strategies())
        module = get_strategy("funding_exhaustion_reversal")
        self.assertEqual(module.spec.default_engine, "polars")
        self.assertEqual(module.spec.signal_mode, "vectorized")

    def test_params_validate(self) -> None:
        params = FundingExhaustionReversalParams()
        self.assertEqual(params.exit_rsi_midline, 50.0)
        with self.assertRaises(ValueError):
            FundingExhaustionReversalParams(rsi_oversold=80.0, rsi_overbought=70.0)

    def test_baseline_rsi_oversold_entry_without_context_columns(self) -> None:
        module = get_strategy("funding_exhaustion_reversal")
        params = FundingExhaustionReversalParams(
            use_context_filters=False,
            require_price_extension=False,
            require_momentum_turn=False,
        )
        result = module.build_signals(_frame().drop("funding_zscore_30"), params)

        self.assertEqual(result.height, _frame().height)
        self.assertEqual(result["timestamp"].to_list(), _frame().sort("timestamp")["timestamp"].to_list())
        self.assertTrue(result["entry_signal"].to_list()[1])
        self.assertIn("exit_signal", result.columns)
        self.assertIn("signal", result.columns)
        self.assertTrue(all(value in (0, 1, None) for value in result["signal"].to_list()))

    def test_negative_funding_oversold_and_improving_momentum_creates_entry(self) -> None:
        module = get_strategy("funding_exhaustion_reversal")
        params = FundingExhaustionReversalParams()
        result = module.build_signals(_frame(), params)
        self.assertTrue(result["entry_signal"].to_list()[1])

    def test_missing_funding_raises_in_context_mode(self) -> None:
        module = get_strategy("funding_exhaustion_reversal")
        params = FundingExhaustionReversalParams(use_context_filters=True)
        with self.assertRaises(ValueError):
            module.build_signals(_frame().drop("funding_zscore_30"), params)

    def test_basis_confirmation_missing_basis_raises(self) -> None:
        module = get_strategy("funding_exhaustion_reversal")
        params = FundingExhaustionReversalParams(require_basis_confirmation=True)
        with self.assertRaises(ValueError):
            module.build_signals(_frame().drop("basis_zscore_60"), params)

    def test_rsi_midline_exit_works(self) -> None:
        module = get_strategy("funding_exhaustion_reversal")
        params = FundingExhaustionReversalParams()
        result = module.build_signals(_frame(), params)
        self.assertTrue(result["exit_signal"].to_list()[3])

    def test_no_forbidden_imports(self) -> None:
        content = open("quant_stack/strategies/funding_exhaustion_reversal/signals.py", encoding="utf-8").read()
        forbidden = ["pandas", "ccxt", "pybit", "requests", "quant_stack.live", "quant_stack.execution", "quant_stack.backtesting", "strategy_families", "engine.backtester"]
        for token in forbidden:
            self.assertNotIn(token, content)


if __name__ == "__main__":
    unittest.main()
