from __future__ import annotations

import io
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import polars as pl

from quant_stack.artifacts import ResearchArtifact, load_artifact, save_artifact
from quant_stack.backtesting import CostModel, PolarsSignalBacktester, ValidationContract, run_monte_carlo, validate_metrics
from quant_stack.backtesting.vectorbt_engine import VectorBTBacktester
from quant_stack.cli.run_live_env import main as live_env_main
from quant_stack.cli.run_research import main as research_main
from quant_stack.indicators.live import BollingerBandState, EMAState, RSIState, RollingStdState
from quant_stack.live import OrderIntent, clamp_position_size
from quant_stack.research import build_research_artifact, is_generated_code_marked


def _signal_frame(prices: list[float], signals: list[int | None]) -> pl.DataFrame:
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 0, 0, 0),
        end=pl.datetime(2024, 1, 1, 0, len(prices) - 1, 0),
        interval="1m",
        eager=True,
    )
    return pl.DataFrame({"timestamp": timestamps, "close": prices, "signal": signals})


class QuantStackBacktestingTests(unittest.TestCase):
    def test_flat_signal_gives_flat_equity(self) -> None:
        result = PolarsSignalBacktester().run(_signal_frame([100.0, 110.0, 120.0], [0, 0, 0]))

        self.assertEqual(result.frame["equity"].to_list(), [1.0, 1.0, 1.0])

    def test_always_long_matches_buy_and_hold_after_lag(self) -> None:
        result = PolarsSignalBacktester().run(_signal_frame([100.0, 110.0, 121.0], [1, 1, 1]))

        self.assertEqual(result.frame["position"].to_list(), [0.0, 1.0, 1.0])
        self.assertAlmostEqual(result.frame["equity"].to_list()[-1], 1.21)

    def test_entry_signal_does_not_profit_from_same_bar(self) -> None:
        result = PolarsSignalBacktester().run(_signal_frame([100.0, 200.0, 200.0], [0, 1, 1]))

        self.assertEqual(result.frame["position"].to_list(), [0.0, 0.0, 1.0])
        self.assertEqual(result.frame["equity"].to_list(), [1.0, 1.0, 1.0])

    def test_fees_apply_only_on_position_changes(self) -> None:
        result = PolarsSignalBacktester(cost_model=CostModel(fee_rate=0.001)).run(
            _signal_frame([100.0, 100.0, 100.0, 100.0], [1, 1, 0, 0])
        )

        self.assertEqual(result.frame["turnover"].to_list(), [0.0, 1.0, 0.0, 1.0])
        self.assertAlmostEqual(result.frame["equity"].to_list()[-1], 0.999 * 0.999)

    def test_validation_contract_and_monte_carlo(self) -> None:
        passed = validate_metrics({"max_drawdown": -0.05, "max_daily_drawdown": -0.01, "cagr": 0.1})
        failed = validate_metrics(
            {"max_drawdown": -0.2, "max_daily_drawdown": -0.01, "cagr": 0.1},
            ValidationContract(max_drawdown_floor=-0.16),
        )
        self.assertTrue(passed.passed)
        self.assertFalse(failed.passed)
        self.assertEqual(run_monte_carlo([], num_simulations=10), (0.0, 0.0))
        self.assertEqual(run_monte_carlo([0.01, -0.02], num_simulations=20, seed=7), run_monte_carlo([0.01, -0.02], num_simulations=20, seed=7))

    def test_vectorbt_adapter_is_importable_without_strategy_coupling(self) -> None:
        adapter = VectorBTBacktester(init_cash=1.0)
        self.assertEqual(adapter.init_cash, 1.0)


class QuantStackLiveStateTests(unittest.TestCase):
    def test_ema_state_matches_expected_sequence_after_warmup(self) -> None:
        state = EMAState(span=3)
        values = [state.step(value) for value in [1.0, 2.0, 3.0, 4.0]]

        self.assertTrue(math.isnan(values[0]))
        self.assertTrue(math.isnan(values[1]))
        self.assertAlmostEqual(values[2], 2.25)
        self.assertAlmostEqual(values[3], 3.125)

    def test_rsi_state_uses_wilder_smoothing(self) -> None:
        state = RSIState(period=3)
        values = [state.step(value) for value in [1.0, 2.0, 3.0, 2.0, 4.0]]

        self.assertAlmostEqual(values[3], 100.0 * (2.0 / 3.0))
        self.assertGreater(values[4], values[3])

    def test_rolling_std_and_bollinger_state(self) -> None:
        rolling = RollingStdState(window=3)
        self.assertTrue(math.isnan(rolling.step(1.0)[0]))
        mean, std = rolling.step(2.0)
        self.assertTrue(math.isnan(mean))
        mean, std = rolling.step(3.0)
        self.assertAlmostEqual(mean, 2.0)
        self.assertAlmostEqual(std, math.sqrt(2.0 / 3.0))

        bands = BollingerBandState(window=3, num_std=1.0)
        _, _, _ = bands.step(1.0)
        _, _, _ = bands.step(2.0)
        middle, upper, lower = bands.step(3.0)
        self.assertAlmostEqual(middle, 2.0)
        self.assertAlmostEqual(upper, 2.0 + math.sqrt(2.0 / 3.0))
        self.assertAlmostEqual(lower, 2.0 - math.sqrt(2.0 / 3.0))

    def test_live_risk_and_order_intent(self) -> None:
        self.assertEqual(clamp_position_size(5.0, max_abs_size=2.0), 2.0)
        self.assertEqual(OrderIntent(symbol="ETH/USDT", side="buy", quantity=1.0).order_type, "market")


class QuantStackResearchAndCliTests(unittest.TestCase):
    def test_research_artifact_marks_generated_code_untrusted_and_roundtrips(self) -> None:
        artifact = build_research_artifact(
            strategy_type="rsi_sma",
            hypothesis="test",
            params={"short_sma": 2},
            generated_code="def backtest_signal(df): return 0.0",
        )
        assert artifact.generated_code is not None
        self.assertTrue(is_generated_code_marked(artifact.generated_code))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "research.json"
            save_artifact(artifact, path)
            loaded = load_artifact(ResearchArtifact, path)
        assert loaded.candidate_params is not None
        self.assertEqual(loaded.candidate_params.strategy_type, "rsi_sma")

    def test_research_cli_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "artifact.json"
            research_main(["--strategy-type", "rsi_sma", "--hypothesis", "test", "--params-json", "{}", "--output", str(output)])
            loaded = load_artifact(ResearchArtifact, output)
        assert loaded.idea is not None
        self.assertEqual(loaded.idea.strategy_type, "rsi_sma")

    def test_live_env_cli_accepts_empty_requirements(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            live_env_main([])
        self.assertIn("passed", buffer.getvalue())

    def test_live_env_cli_requires_named_env(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                live_env_main(["--required", "MISSING_KEY"])


if __name__ == "__main__":
    unittest.main()
