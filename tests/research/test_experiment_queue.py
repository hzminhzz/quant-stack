from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.schemas import CandidateParams, ExperimentPlan, ExperimentStatus, RejectionReason


def valid_plan() -> ExperimentPlan:
    return ExperimentPlan(
        strategy_name="rsi_sma",
        params_to_test=[CandidateParams(strategy_name="rsi_sma", params={}, rationale="baseline")],
        symbols=["BTC"],
        timeframes=["1m"],
        train_period="2021-2023",
        test_period="2024",
        validation_method="walk-forward",
        acceptance_criteria=["max drawdown above -16%"],
    )


class ExperimentQueueTests(unittest.TestCase):
    def test_state_transitions_work_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "queue.json"
            queue = ExperimentQueue(path)
            record = queue.submit(valid_plan(), created_by_agent="planner")
            self.assertEqual(record.status, ExperimentStatus.PROPOSED)
            approved = queue.transition(record.experiment_id, ExperimentStatus.APPROVED)
            self.assertEqual(approved.status, ExperimentStatus.APPROVED)
            running = queue.transition(record.experiment_id, ExperimentStatus.RUNNING)
            self.assertEqual(running.status, ExperimentStatus.RUNNING)
            completed = queue.transition(record.experiment_id, ExperimentStatus.COMPLETED, result_path="artifacts/result.json")
            self.assertEqual(completed.result_path, "artifacts/result.json")

            reloaded = ExperimentQueue(path)
            self.assertEqual(reloaded.get(record.experiment_id).status, ExperimentStatus.COMPLETED)

    def test_invalid_transition_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = ExperimentQueue(Path(tmpdir) / "queue.json")
            record = queue.submit(valid_plan(), created_by_agent="planner")

            with self.assertRaises(ValueError):
                queue.transition(record.experiment_id, ExperimentStatus.COMPLETED)

    def test_rejection_records_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = ExperimentQueue(Path(tmpdir) / "queue.json")
            record = queue.submit(valid_plan(), created_by_agent="planner")
            rejected = queue.transition(
                record.experiment_id,
                ExperimentStatus.REJECTED,
                rejection_reason=RejectionReason(code="bad_plan", message="bad", severity="high"),
            )

            assert rejected.rejection_reason is not None
            self.assertEqual(rejected.rejection_reason.code, "bad_plan")


if __name__ == "__main__":
    unittest.main()
