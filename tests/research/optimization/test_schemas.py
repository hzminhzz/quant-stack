from __future__ import annotations

import unittest

from quant_stack.research.optimization.schemas import AcceptanceCriteria, OptimizationRequest, StrategyPatchProposal


class OptimizationSchemaTests(unittest.TestCase):
    def test_request_model_roundtrip(self) -> None:
        request = OptimizationRequest(
            strategy_name="rsi_sma",
            symbols=["BTC"],
            timeframes=["1m"],
            train_period="2021-2023",
            test_period="2024",
            max_iterations=2,
            objective_name="oos_robustness",
            acceptance_criteria=AcceptanceCriteria(),
            allowed_change_types=["params", "logic"],
        )
        self.assertEqual(request.strategy_name, "rsi_sma")
        self.assertEqual(request.max_iterations, 2)

    def test_patch_proposal_requires_rationale(self) -> None:
        proposal = StrategyPatchProposal(
            strategy_name="rsi_sma",
            change_type="params",
            params={"rsi_period": 12},
            rationale="Tighten reversion threshold",
            expected_effect="better oos sharpe",
            risks=["fewer trades"],
        )
        self.assertEqual(proposal.change_type, "params")


if __name__ == "__main__":
    unittest.main()
