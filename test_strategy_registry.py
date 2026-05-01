from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl

from pipeline_artifacts import (
    ResearchArtifact,
    SignalArtifact,
    ValidationArtifact,
    load_research_artifact,
    load_signal_artifact,
    load_validation_artifact,
    save_research_artifact,
    save_signal_artifact,
    save_validation_artifact,
)
from strategy_families import available_strategy_families, get_strategy_family


class StrategyRegistryTests(unittest.TestCase):
    def test_available_families_include_bb_and_rsi(self) -> None:
        self.assertEqual(available_strategy_families(), ["bb", "rsi"])

    def test_bb_family_validates_and_formats_params(self) -> None:
        family = get_strategy_family("bb")
        params = family.validate_params({"bb_length": 20, "bb_std": 1.5, "regime_sma": 200})
        self.assertIn("BB Strategy", family.format_params(params))

    def test_rsi_family_rejects_invalid_window_order(self) -> None:
        family = get_strategy_family("rsi")
        with self.assertRaises(ValueError):
            family.validate_params({
                "short_sma": 50,
                "long_sma": 20,
                "rsi_period": 14,
                "rsi_threshold": 40.0,
                "rsi_side": "below",
            })

    def test_validation_artifact_roundtrip(self) -> None:
        artifact = ValidationArtifact(
            strategy_type="bb",
            params={"bb_length": 20, "bb_std": 1.5, "regime_sma": 200},
            rationale="ok",
            in_sample_metrics={"cagr": 0.1, "max_drawdown": -0.1, "max_daily_drawdown": -0.02, "time_in_market": 0.5, "max_consecutive_losing_days": 3, "smart_sharpe": 1.0, "smart_sortino": 1.2, "tail_ratio": 1.1, "gain_pain_ratio": 1.1, "kelly_criterion": 0.2, "cumulative_return": 0.1},
            in_sample_trade_count=50,
            out_of_sample_metrics={"cagr": 0.05, "max_drawdown": -0.08, "max_daily_drawdown": -0.02, "time_in_market": 0.5, "max_consecutive_losing_days": 2, "smart_sharpe": 0.8, "smart_sortino": 1.0, "tail_ratio": 1.1, "gain_pain_ratio": 1.1, "kelly_criterion": 0.1, "cumulative_return": 0.05},
            out_of_sample_trade_count=20,
            monte_carlo_95_dd_absolute_pct=12.5,
            monte_carlo_median_dd_absolute_pct=8.0,
            approved=True,
            critique="ok",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "artifact.json"
            save_validation_artifact(artifact, path)
            loaded = load_validation_artifact(path)
            self.assertEqual(loaded.strategy_type, "bb")
            self.assertTrue(loaded.approved)

    def test_signal_and_research_artifact_roundtrip(self) -> None:
        signal_artifact = SignalArtifact(
            strategy_type="rsi",
            signal={"asset": "BTC", "params": {"short_sma": 20, "long_sma": 50, "rsi_period": 14, "rsi_threshold": 35.0, "rsi_side": "below"}, "hypothesis": "SMA crossover with RSI dip-buying", "stop_loss_pct": 2.5},
            source="paper.html",
            paper_context="ctx",
        )
        research_artifact = ResearchArtifact(
            strategy_type="rsi",
            signal=signal_artifact.signal,
            paper_context="ctx",
            polars_code="def backtest_signal(...): pass",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "signal.json"
            research_path = Path(tmpdir) / "research.json"
            save_signal_artifact(signal_artifact, signal_path)
            save_research_artifact(research_artifact, research_path)
            loaded_signal = load_signal_artifact(signal_path)
            loaded_research = load_research_artifact(research_path)
            self.assertEqual(loaded_signal.strategy_type, "rsi")
            self.assertEqual(loaded_research.strategy_type, "rsi")

    def test_rsi_family_signal_model_and_query_are_family_native(self) -> None:
        family = get_strategy_family("rsi")
        signal = family.signal_model().model_validate(
            {
                "asset": "BTC",
                "params": {
                    "short_sma": 20,
                    "long_sma": 50,
                    "rsi_period": 14,
                    "rsi_threshold": 35.0,
                    "rsi_side": "below",
                },
                "hypothesis": "SMA crossover with RSI dip-buying",
                "stop_loss_pct": 2.5,
            }
        )
        self.assertEqual(signal.params.short_sma, 20)
        self.assertIn("params=", family.build_seed_hint(signal.model_dump()))

    def test_family_prepare_market_data_respects_family_timeframe(self) -> None:
        rsi_family = get_strategy_family("rsi")
        bb_family = get_strategy_family("bb")
        df = pl.DataFrame({
            "timestamp": [
                __import__("datetime").datetime(2024, 1, 1, 0, 0),
                __import__("datetime").datetime(2024, 1, 1, 1, 0),
                __import__("datetime").datetime(2024, 1, 1, 2, 0),
                __import__("datetime").datetime(2024, 1, 1, 3, 0),
                __import__("datetime").datetime(2024, 1, 1, 4, 0),
            ],
            "open": [1, 2, 3, 4, 5],
            "high": [1, 2, 3, 4, 5],
            "low": [1, 2, 3, 4, 5],
            "close": [1, 2, 3, 4, 5],
            "volume": [1, 1, 1, 1, 1],
        })
        self.assertEqual(len(rsi_family.prepare_market_data(df)), 5)
        self.assertLessEqual(len(bb_family.prepare_market_data(df)), 2)


if __name__ == "__main__":
    unittest.main()
