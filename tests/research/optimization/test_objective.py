from __future__ import annotations

import unittest

from quant_stack.research.optimization.objective import score_objective
from quant_stack.research.optimization.schemas import AcceptanceCriteria
from quant_stack.research.schemas import BacktestSummary, ValidationReport


def _summary(**metrics: float) -> BacktestSummary:
    return BacktestSummary(
        strategy_name="rsi_sma",
        symbol="BTC",
        timeframe="1m",
        metrics=metrics,
        major_weaknesses=[],
        pass_fail="pass",
        artifact_path="artifacts/research/tmp.json",
    )


class ObjectiveTests(unittest.TestCase):
    def test_low_trade_count_is_rejected(self) -> None:
        criteria = AcceptanceCriteria(min_trades=20)
        summary = _summary(trade_count=5, oos_sharpe=1.0, max_drawdown=-0.05, oos_return=0.1)
        validation = ValidationReport(passed=True, reasons=[], metrics=summary.metrics, risk_flags=[], artifact_path="a.json")
        score = score_objective(summary, validation, criteria)
        self.assertFalse(score.passed)
        self.assertIn("low_trade_count", score.failure_reasons)

    def test_is_oos_gap_is_penalized(self) -> None:
        criteria = AcceptanceCriteria(max_is_oos_sharpe_gap=0.4)
        summary = _summary(trade_count=40, is_sharpe=2.0, oos_sharpe=0.5, max_drawdown=-0.08, oos_return=0.05)
        validation = ValidationReport(passed=True, reasons=[], metrics=summary.metrics, risk_flags=[], artifact_path="a.json")
        score = score_objective(summary, validation, criteria)
        self.assertIn("is_oos_sharpe_gap_too_large", score.failure_reasons)
        self.assertGreater(score.penalties["overfit_gap_penalty"], 0.0)

    def test_high_drawdown_is_rejected(self) -> None:
        criteria = AcceptanceCriteria(max_drawdown=0.10)
        summary = _summary(trade_count=50, oos_sharpe=1.0, max_drawdown=-0.30, oos_return=0.1)
        validation = ValidationReport(passed=True, reasons=[], metrics=summary.metrics, risk_flags=[], artifact_path="a.json")
        score = score_objective(summary, validation, criteria)
        self.assertFalse(score.passed)
        self.assertIn("max_drawdown_exceeded", score.failure_reasons)

    def test_score_is_deterministic(self) -> None:
        criteria = AcceptanceCriteria()
        summary = _summary(
            trade_count=30,
            oos_sharpe=0.8,
            is_sharpe=1.1,
            max_drawdown=-0.09,
            max_daily_drawdown=-0.02,
            turnover=0.5,
            profit_factor=1.3,
            walk_forward_pass_rate=0.7,
            oos_return=0.2,
        )
        validation = ValidationReport(passed=True, reasons=[], metrics=summary.metrics, risk_flags=[], artifact_path="a.json")
        first = score_objective(summary, validation, criteria)
        second = score_objective(summary, validation, criteria)
        self.assertEqual(first.model_dump(), second.model_dump())


if __name__ == "__main__":
    unittest.main()
