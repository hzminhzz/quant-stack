from __future__ import annotations

import unittest

import polars as pl

from quant_stack.strategies import available_strategies, get_strategy
from quant_stack.strategies.forced_flow_band_reclaim.params import ForcedFlowBandReclaimParams


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
            "close": [99.0, 98.0, 97.0, 100.0, 101.0],
            "bb_mid_20": [100.0, 100.0, 100.0, 100.0, 100.0],
            "bb_lower_20": [98.0, 98.0, 98.0, 98.0, 98.0],
            "bb_reclaim_lower": [False, False, True, False, False],
            "bb_reclaim_lower_strict": [False, False, True, False, False],
            "liquidation_proxy_long": [False, False, True, False, False],
            "forced_selling_proxy": [False, False, True, False, False],
            "oi_flush": [False, False, True, False, False],
            "funding_zscore_30": [-0.2, -0.4, -1.8, -0.3, 0.1],
            "basis_zscore_60": [-0.2, -0.5, -1.2, -0.1, 0.2],
            "spread_bps": [3.0, 3.0, 2.0, 2.0, 2.0],
        }
    )


class ForcedFlowBandReclaimTests(unittest.TestCase):
    def test_module_imports_and_registry_entry(self) -> None:
        self.assertIn("forced_flow_band_reclaim", available_strategies())
        module = get_strategy("forced_flow_band_reclaim")
        self.assertEqual(module.spec.default_engine, "polars")
        self.assertEqual(module.spec.signal_mode, "vectorized")

    def test_params_validate(self) -> None:
        params = ForcedFlowBandReclaimParams(max_spread_bps=5.0)
        self.assertEqual(params.max_spread_bps, 5.0)
        with self.assertRaises(ValueError):
            ForcedFlowBandReclaimParams(max_spread_bps=-1.0)

    def test_baseline_lower_reclaim_creates_entry_and_mid_band_exit(self) -> None:
        module = get_strategy("forced_flow_band_reclaim")
        params = ForcedFlowBandReclaimParams(
            use_context_filters=False,
            require_forced_flow_proxy=False,
            use_strict_reclaim=False,
        )
        result = module.build_signals(_frame(), params)

        self.assertEqual(result.height, _frame().height)
        self.assertEqual(result["timestamp"].to_list(), _frame().sort("timestamp")["timestamp"].to_list())
        self.assertIn("entry_signal", result.columns)
        self.assertIn("exit_signal", result.columns)
        self.assertIn("signal", result.columns)
        self.assertTrue(result["entry_signal"].to_list()[2])
        self.assertTrue(result["exit_signal"].to_list()[3])
        self.assertEqual(set(result["signal"].drop_nulls().to_list()), {0, 1})

    def test_require_forced_flow_proxy_blocks_entry_when_false(self) -> None:
        module = get_strategy("forced_flow_band_reclaim")
        params = ForcedFlowBandReclaimParams(require_forced_flow_proxy=True, use_context_filters=True)
        df = _frame().with_columns(pl.lit(False).alias("liquidation_proxy_long"), pl.lit(False).alias("forced_selling_proxy"))
        result = module.build_signals(df, params)
        self.assertFalse(any(result["entry_signal"].to_list()))

    def test_require_oi_flush_blocks_entry_when_false(self) -> None:
        module = get_strategy("forced_flow_band_reclaim")
        params = ForcedFlowBandReclaimParams(require_oi_flush=True, use_context_filters=True)
        df = _frame().with_columns(pl.lit(False).alias("oi_flush"))
        result = module.build_signals(df, params)
        self.assertFalse(any(result["entry_signal"].to_list()))

    def test_strict_reclaim_used_when_enabled(self) -> None:
        module = get_strategy("forced_flow_band_reclaim")
        params = ForcedFlowBandReclaimParams(use_context_filters=False, use_strict_reclaim=True, require_forced_flow_proxy=False)
        df = _frame().with_columns(
            pl.col("bb_reclaim_lower").fill_null(False),
            pl.lit(False).alias("bb_reclaim_lower_strict"),
        )
        result = module.build_signals(df, params)
        self.assertFalse(any(result["entry_signal"].to_list()))

    def test_context_mode_missing_columns_raises(self) -> None:
        module = get_strategy("forced_flow_band_reclaim")
        params = ForcedFlowBandReclaimParams(require_forced_flow_proxy=True, use_context_filters=True)
        with self.assertRaises(ValueError):
            module.build_signals(_frame().drop("liquidation_proxy_long", "forced_selling_proxy"), params)

    def test_no_forbidden_imports(self) -> None:
        content = open("quant_stack/strategies/forced_flow_band_reclaim/signals.py", encoding="utf-8").read()
        forbidden = ["pandas", "ccxt", "pybit", "requests", "quant_stack.live", "quant_stack.execution", "quant_stack.backtesting", "strategy_families", "engine.backtester"]
        for token in forbidden:
            self.assertNotIn(token, content)


if __name__ == "__main__":
    unittest.main()
