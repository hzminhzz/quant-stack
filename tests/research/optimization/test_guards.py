from __future__ import annotations

import ast
import inspect
import unittest

from quant_stack.research.optimization.guards import guard_patch_proposal, params_fingerprint
from quant_stack.research.optimization.schemas import StrategyPatchProposal
import quant_stack.research.optimization.loop as optimization_loop


class OptimizationGuardTests(unittest.TestCase):
    def test_unsafe_proposal_is_rejected(self) -> None:
        proposal = StrategyPatchProposal(
            strategy_name="rsi_sma",
            change_type="logic",
            logic_changes=["use future data shift(-1) for entries"],
            rationale="improve performance using future data",
            expected_effect="higher sharpe",
            risks=[],
        )
        reasons = guard_patch_proposal(proposal, allowed_change_types={"params", "logic"})
        self.assertTrue(any(reason.code == "forbidden_proposal_term" for reason in reasons))

    def test_live_broker_access_proposal_is_rejected(self) -> None:
        proposal = StrategyPatchProposal(
            strategy_name="rsi_sma",
            change_type="logic",
            logic_changes=["place order through broker adapter on signal"],
            rationale="connect directly to broker",
            expected_effect="faster fills",
            risks=[],
        )
        reasons = guard_patch_proposal(proposal, allowed_change_types={"logic"})
        self.assertTrue(any("forbidden term: broker" in reason.message for reason in reasons))

    def test_duplicate_params_are_rejected(self) -> None:
        proposal = StrategyPatchProposal(
            strategy_name="rsi_sma",
            change_type="params",
            params={"rsi_period": 14},
            rationale="retest existing params",
            expected_effect="confirm stability",
            risks=[],
        )
        reasons = guard_patch_proposal(
            proposal,
            allowed_change_types={"params"},
            tested_param_fingerprints={params_fingerprint({"rsi_period": 14})},
        )
        self.assertTrue(any(reason.code == "duplicate_params" for reason in reasons))

    def test_optimizer_loop_has_no_live_execution_imports(self) -> None:
        source = inspect.getsource(optimization_loop)
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

        forbidden = ("ccxt", "subprocess", "quant_stack.live", "broker")
        self.assertTrue(all(not module.startswith(forbidden) for module in imported))


if __name__ == "__main__":
    unittest.main()
