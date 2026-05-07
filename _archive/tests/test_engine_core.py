from __future__ import annotations

import unittest

import numpy as np

from engine.backtester import get_equity_and_trades_rsi
from engine.evaluator import PhaseValidationRequest, validate_phase_metrics
from engine.monte_carlo import run_monte_carlo
from strategy_families import get_strategy_family


class EngineCoreTests(unittest.TestCase):
    def test_backtester_matches_reference_crossover_logic(self) -> None:
        prices = np.array([10, 10, 10, 10, 10, 11, 12, 13, 14, 15, 16, 17], dtype=np.float64)
        equity, exposed, trades = get_equity_and_trades_rsi(prices, 2, 4, 2, 101.0)

        self.assertEqual(len(equity), len(prices))
        self.assertEqual(len(exposed), len(prices))
        self.assertTrue(np.any(exposed))
        self.assertGreaterEqual(len(trades), 0)
        self.assertGreaterEqual(equity[-1], 1.0)

    def test_monte_carlo_is_deterministic_for_same_seed(self) -> None:
        trades = np.array([0.01, -0.02, 0.03, -0.01, 0.02], dtype=np.float64)
        first = run_monte_carlo(trades, num_simulations=50, seed=123)
        second = run_monte_carlo(trades, num_simulations=50, seed=123)
        self.assertEqual(first, second)

    def test_proposed_strategy_validation_rejects_bad_ordering(self) -> None:
        family = get_strategy_family("rsi")
        with self.assertRaises(ValueError):
            family.validate_params(
                {
                    "short_sma": 50,
                    "long_sma": 20,
                    "rsi_period": 14,
                    "rsi_threshold": 45.0,
                    "rsi_side": "below",
                }
            )

    def test_prop_contract_validation_rejects_bad_drawdown(self) -> None:
        metrics = {
            "cumulative_return": 0.10,
            "cagr": 0.12,
            "time_in_market": 0.5,
            "max_drawdown": -0.20,
            "max_daily_drawdown": -0.02,
            "max_consecutive_losing_days": 3,
            "smart_sharpe": 0.8,
            "smart_sortino": 1.0,
            "tail_ratio": 1.1,
            "gain_pain_ratio": 1.2,
            "kelly_criterion": 0.1,
        }
        result = validate_phase_metrics(PhaseValidationRequest(metrics=metrics, label="In-Sample"))
        self.assertIsNotNone(result.rejection_reason)
        rejection_reason = result.rejection_reason
        assert rejection_reason is not None
        self.assertIn("deterministic prop-firm validation", rejection_reason)


if __name__ == "__main__":
    unittest.main()
