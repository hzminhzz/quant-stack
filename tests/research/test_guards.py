from __future__ import annotations

import unittest

from quant_stack.research.guards import guard_experiment_plan, guard_strategy_idea
from quant_stack.research.schemas import CandidateParams, ExperimentPlan
from tests.research.test_schemas import valid_idea


class ResearchGuardTests(unittest.TestCase):
    def test_valid_idea_is_not_rejected(self) -> None:
        reasons = guard_strategy_idea(valid_idea(), available_features={"close", "rsi"})

        self.assertEqual(reasons, [])

    def test_vague_strategy_idea_is_rejected(self) -> None:
        idea = valid_idea().model_copy(update={"entry_logic": "AI decides", "exit_logic": "some signal"})

        reasons = guard_strategy_idea(idea)

        self.assertTrue(any(reason.code == "vague_logic" for reason in reasons))

    def test_future_data_idea_is_rejected(self) -> None:
        idea = valid_idea().model_copy(update={"entry_logic": "Enter using next close and future data."})

        reasons = guard_strategy_idea(idea)

        self.assertTrue(any(reason.code == "forbidden_research_claim" for reason in reasons))

    def test_experiment_plan_rejects_bad_symbol_timeframe_and_live_paths(self) -> None:
        plan = ExperimentPlan(
            strategy_name="rsi_sma",
            params_to_test=[CandidateParams(strategy_name="rsi_sma", params={}, rationale="baseline")],
            symbols=["DOGE"],
            timeframes=["2s"],
            train_period="2021",
            test_period="2022",
            validation_method="bypass validation and call broker",
            acceptance_criteria=["guaranteed profit"],
        )

        reasons = guard_experiment_plan(
            plan,
            registered_strategies={"rsi_sma"},
            approved_symbols={"BTC"},
            approved_timeframes={"1m"},
        )

        self.assertTrue(any(reason.code == "unapproved_symbol" for reason in reasons))
        self.assertTrue(any(reason.code == "unapproved_timeframe" for reason in reasons))
        self.assertTrue(any(reason.code == "forbidden_research_claim" for reason in reasons))


if __name__ == "__main__":
    unittest.main()
