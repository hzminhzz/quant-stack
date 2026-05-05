from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_stack.artifacts.store import load_artifact
from quant_stack.research.optimization.loop import run_optimization_loop
from quant_stack.research.optimization.memory import OptimizationMemorySnapshot
from quant_stack.research.optimization.schemas import (
    AcceptanceCriteria,
    BacktestCritique,
    OptimizationRequest,
    OptimizationResult,
    StrategyPatchProposal,
)


class StubCritic:
    async def critique(self, *, summary, validation) -> BacktestCritique:
        return BacktestCritique(
            approved=True,
            summary="LLM approves",
            failure_modes=[],
            suspected_overfit=False,
            lookahead_risk=False,
            metric_weaknesses=[],
            next_suggestions=["try another threshold"],
        )


class StubOptimizerAlwaysSame:
    async def propose(self, *, request, latest_summary, critique, prior_params):
        return StrategyPatchProposal(
            strategy_name=request.strategy_name,
            change_type="params",
            params={"rsi_period": 14},
            rationale="tighten RSI period",
            expected_effect="improve oos",
            risks=["less trades"],
        )


class StubOptimizerUnsafe:
    async def propose(self, *, request, latest_summary, critique, prior_params):
        return StrategyPatchProposal(
            strategy_name=request.strategy_name,
            change_type="logic",
            logic_changes=["place order via broker"],
            rationale="wire to broker",
            expected_effect="instant execution",
            risks=["none"],
        )


class OptimizationLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_loop_stops_after_max_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = OptimizationRequest(
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                train_period="2021-2023",
                test_period="2024",
                max_iterations=2,
                objective_name="oos_robustness",
                acceptance_criteria=AcceptanceCriteria(min_trades=9999),
                allowed_change_types=["params"],
            )
            result = await run_optimization_loop(
                request,
                optimizer=StubOptimizerAlwaysSame(),
                critic=StubCritic(),
                queue_path=Path(tmpdir) / "queue.json",
                memory_path=Path(tmpdir) / "memory.json",
                artifact_dir=Path(tmpdir) / "artifacts",
            )
            self.assertIsInstance(result, OptimizationResult)
            self.assertFalse(result.approved)

    async def test_repeated_candidate_params_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = OptimizationRequest(
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                train_period="2021-2023",
                test_period="2024",
                max_iterations=3,
                objective_name="oos_robustness",
                acceptance_criteria=AcceptanceCriteria(min_trades=9999),
                allowed_change_types=["params"],
            )
            result = await run_optimization_loop(
                request,
                optimizer=StubOptimizerAlwaysSame(),
                critic=StubCritic(),
                queue_path=Path(tmpdir) / "queue.json",
                memory_path=Path(tmpdir) / "memory.json",
                artifact_dir=Path(tmpdir) / "artifacts",
            )
            snapshot = load_artifact(OptimizationMemorySnapshot, Path(tmpdir) / "memory.json")
            self.assertTrue(any(candidate.status == "skipped" for candidate in snapshot.candidates))
            self.assertFalse(result.approved)

    async def test_deterministic_gate_overrides_llm_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = OptimizationRequest(
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                train_period="2021-2023",
                test_period="2024",
                max_iterations=1,
                objective_name="oos_robustness",
                acceptance_criteria=AcceptanceCriteria(min_trades=9999),
                allowed_change_types=["params"],
            )
            result = await run_optimization_loop(
                request,
                optimizer=StubOptimizerAlwaysSame(),
                critic=StubCritic(),
                queue_path=Path(tmpdir) / "queue.json",
                memory_path=Path(tmpdir) / "memory.json",
                artifact_dir=Path(tmpdir) / "artifacts",
            )
            self.assertFalse(result.approved)

    async def test_unsafe_proposals_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = OptimizationRequest(
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                train_period="2021-2023",
                test_period="2024",
                max_iterations=1,
                objective_name="oos_robustness",
                acceptance_criteria=AcceptanceCriteria(),
                allowed_change_types=["logic"],
            )
            result = await run_optimization_loop(
                request,
                optimizer=StubOptimizerUnsafe(),
                critic=StubCritic(),
                queue_path=Path(tmpdir) / "queue.json",
                memory_path=Path(tmpdir) / "memory.json",
                artifact_dir=Path(tmpdir) / "artifacts",
            )
            self.assertFalse(result.approved)


if __name__ == "__main__":
    unittest.main()
