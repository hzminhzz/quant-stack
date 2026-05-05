from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_stack.research.optimization.memory import OptimizationMemory
from quant_stack.research.optimization.schemas import OptimizationCandidate, StrategyPatchProposal


class OptimizationMemoryTests(unittest.TestCase):
    def test_repeated_candidate_params_are_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "memory.json"
            memory = OptimizationMemory(path, run_id="run-1")
            candidate = OptimizationCandidate(
                candidate_id="c1",
                proposal=StrategyPatchProposal(
                    strategy_name="rsi_sma",
                    change_type="params",
                    params={"rsi_period": 14},
                    rationale="repeatability test",
                    expected_effect="stable",
                    risks=[],
                ),
            )
            memory.add_candidate(candidate)

            reloaded = OptimizationMemory(path, run_id="run-1")
            self.assertIn('{"rsi_period":14}', reloaded.tested_param_fingerprints())


if __name__ == "__main__":
    unittest.main()
