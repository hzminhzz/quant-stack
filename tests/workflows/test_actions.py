from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.optimization.schemas import AcceptanceCriteria
from quant_stack.workflows.actions import QueueOptimizationAction
from quant_stack.workflows.schemas import WorkflowDefinition, WorkflowEvent


class ActionTests(unittest.TestCase):
    def test_action_creates_request_and_enqueues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = ExperimentQueue(Path(tmpdir) / "queue.json")
            action = QueueOptimizationAction(queue)
            definition = WorkflowDefinition(
                workflow_id="wf-1",
                strategy_name="rsi_sma",
                symbols=["BTC"],
                timeframes=["1m"],
                acceptance_criteria=AcceptanceCriteria(),
                context_filters={"spread_bps_max": 15},
            )
            event = WorkflowEvent(event_id="evt-1", event_type="context", symbol="BTC", timeframe="1m", context_tags=["risk_off"])
            request_id, request = action.run(definition, event, train_period="2021-2023", test_period="2024")

            self.assertTrue(request_id.startswith("optreq-"))
            self.assertEqual(request.created_by, "workflow")
            self.assertEqual(request.source_event_id, "evt-1")
            self.assertEqual(request.context_filters.get("spread_bps_max"), 15)
            queued = queue.list_optimization_requests()
            self.assertEqual(len(queued), 1)


if __name__ == "__main__":
    unittest.main()
