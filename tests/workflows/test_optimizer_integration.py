from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_stack.research.experiment_queue import ExperimentQueue, OptimizationRequestStatus
from quant_stack.research.optimization.schemas import AcceptanceCriteria, OptimizationResult, OptimizationRequest
from quant_stack.research.optimization.worker import OptimizationWorker


class OptimizerIntegrationTests(unittest.TestCase):
    def test_optimizer_worker_consumes_approved_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            queue = ExperimentQueue(queue_path)
            request = OptimizationRequest(
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                train_period="2021-2023",
                test_period="2024",
                max_iterations=2,
                acceptance_criteria=AcceptanceCriteria(),
                allowed_change_types=["params"],
                created_by="workflow",
                source_event_id="evt-1",
                context_filters={"regime": "risk_off"},
            )
            record = queue.submit_optimization_request(request, auto_approve=True)

            async def fake_run(*args, **kwargs):
                return OptimizationResult(
                    run_id="opt-1",
                    best_candidate=None,
                    best_score=None,
                    approved=False,
                    summary="done",
                    artifact_path=str(Path(tmpdir) / "result.json"),
                )

            worker = OptimizationWorker(queue_path=queue_path)
            with patch("quant_stack.research.optimization.worker.run_optimization_loop", side_effect=fake_run):
                result_path = worker.run_once()

            self.assertIsNotNone(result_path)
            updated = ExperimentQueue(queue_path).list_optimization_requests()[0]
            self.assertEqual(updated.status, OptimizationRequestStatus.FAILED)

    def test_unsafe_auto_approved_logic_change_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            queue = ExperimentQueue(queue_path)
            request = OptimizationRequest(
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                train_period="2021-2023",
                test_period="2024",
                max_iterations=2,
                acceptance_criteria=AcceptanceCriteria(),
                allowed_change_types=["logic"],
                created_by="workflow",
                source_event_id="evt-2",
            )
            queue.submit_optimization_request(request, auto_approve=True)

            worker = OptimizationWorker(queue_path=queue_path)
            result = worker.run_once()
            self.assertIsNone(result)
            updated = ExperimentQueue(queue_path).list_optimization_requests()[0]
            self.assertEqual(updated.status, OptimizationRequestStatus.REJECTED)
            self.assertIsNotNone(updated.rejection_reason)


if __name__ == "__main__":
    unittest.main()
