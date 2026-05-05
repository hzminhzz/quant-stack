from __future__ import annotations

import unittest

from pydantic import ValidationError

from quant_stack.research.agents import BacktestCriticAgent
from quant_stack.research.schemas import (
    BacktestSummary,
    CandidateParams,
    ExperimentPlan,
    ResearchCritique,
    StrategyIdea,
    ValidationReport,
)


def valid_idea() -> StrategyIdea:
    return StrategyIdea(
        name="RSI pullback",
        hypothesis="Mean-reversion pullbacks recover during calm upward regimes.",
        asset_class="crypto",
        timeframe="1m",
        required_features=["close", "rsi"],
        entry_logic="Enter when RSI crosses below threshold and trend filter is positive.",
        exit_logic="Exit when RSI normalizes or the trend filter turns negative.",
        risk_logic="Use fixed fractional exposure and reject if drawdown exceeds validation limits.",
        expected_regime="calm bull trend",
        failure_modes=["trend crash", "liquidity shock"],
        source_notes=["paper section 3"],
        confidence=0.6,
    )


class ResearchSchemaTests(unittest.TestCase):
    def test_valid_strategy_idea_validates(self) -> None:
        idea = valid_idea()

        self.assertEqual(idea.name, "RSI pullback")
        self.assertEqual(idea.confidence, 0.6)

    def test_invalid_strategy_idea_fails_schema(self) -> None:
        with self.assertRaises(ValidationError):
            StrategyIdea(
                name="x",
                hypothesis="short",
                asset_class="crypto",
                timeframe="1m",
                required_features=[],
                entry_logic="x",
                exit_logic="x",
                risk_logic="x",
                expected_regime="x",
                failure_modes=[],
                confidence=2.0,
            )

    def test_experiment_plan_normalizes_symbols_timeframes(self) -> None:
        plan = ExperimentPlan(
            strategy_name="rsi_sma",
            params_to_test=[CandidateParams(strategy_name="rsi_sma", params={}, rationale="baseline", constraints=[])],
            symbols=["btc"],
            timeframes=["1M"],
            train_period="2021-2023",
            test_period="2024",
            validation_method="walk-forward",
            acceptance_criteria=["max drawdown above -16%"],
        )

        self.assertEqual(plan.symbols, ["BTC"])
        self.assertEqual(plan.timeframes, ["1m"])

    def test_backtest_critic_output_validates_as_research_critique(self) -> None:
        critique = BacktestCriticAgent.validate_output(
            {
                "lookahead_risk": "low; shifted signals are used",
                "overfit_risk": "medium; params need walk-forward",
                "data_snooping_risk": "medium; multiple ideas reviewed",
                "execution_risk": "low; market orders only in deterministic test",
                "market_regime_risk": "high; tested on one regime",
                "suggested_tests": ["walk-forward", "fee sensitivity"],
                "verdict": "revise",
            }
        )

        self.assertIsInstance(critique, ResearchCritique)
        self.assertEqual(critique.verdict, "revise")

    def test_backtest_and_validation_reports_validate(self) -> None:
        summary = BacktestSummary(
            strategy_name="rsi_sma",
            symbol="BTC",
            timeframe="1m",
            metrics={"cagr": 0.1},
            major_weaknesses=[],
            pass_fail="pass",
            artifact_path="artifacts/test.json",
        )
        report = ValidationReport(passed=True, metrics=summary.metrics, artifact_path="artifacts/validation.json")

        self.assertTrue(report.passed)
        self.assertEqual(summary.pass_fail, "pass")


if __name__ == "__main__":
    unittest.main()
