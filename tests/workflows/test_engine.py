from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import inspect

from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.optimization.schemas import AcceptanceCriteria
from quant_stack.workflows.actions import QueueOptimizationAction
from quant_stack.workflows.cooldown import CooldownStore
import quant_stack.workflows.engine as engine_module
from quant_stack.workflows.engine import WorkflowEngine
from quant_stack.workflows.registry import WorkflowRegistry
from quant_stack.workflows.schemas import WorkflowDefinition, WorkflowEvent
from quant_stack.workflows.triggers import ContextTagTrigger


class EngineTests(unittest.TestCase):
    def _engine(self, queue: ExperimentQueue) -> tuple[WorkflowEngine, WorkflowRegistry]:
        registry = WorkflowRegistry()
        engine = WorkflowEngine(
            registry=registry,
            trigger=ContextTagTrigger(),
            action=QueueOptimizationAction(queue),
            cooldown_store=CooldownStore(),
        )
        return engine, registry

    def test_cooldown_prevents_spam(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = ExperimentQueue(Path(tmpdir) / "queue.json")
            engine, registry = self._engine(queue)
            registry.register(
                WorkflowDefinition(
                    workflow_id="wf-1",
                    strategy_name="rsi_sma",
                    symbols=["BTC"],
                    timeframes=["1m"],
                    required_context_tags=["risk_off"],
                    cooldown_seconds=3600,
                    acceptance_criteria=AcceptanceCriteria(),
                )
            )
            event = WorkflowEvent(event_id="evt-1", event_type="context", symbol="BTC", timeframe="1m", context_tags=["risk_off"])
            first = engine.handle_event(event, train_period="2021-2023", test_period="2024")
            second = engine.handle_event(event.model_copy(update={"event_id": "evt-2"}), train_period="2021-2023", test_period="2024")

            self.assertTrue(first[0].triggered)
            self.assertFalse(second[0].triggered)
            self.assertEqual(second[0].reason, "cooldown_active")

    def test_engine_does_not_call_optimizer_loop(self) -> None:
        # Structural boundary assertion: engine only queues via action/queue.
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = ExperimentQueue(Path(tmpdir) / "queue.json")
            engine, registry = self._engine(queue)
            registry.register(
                WorkflowDefinition(
                    workflow_id="wf-2",
                    strategy_name="rsi_sma",
                    symbols=["BTC"],
                    timeframes=["1m"],
                    required_context_tags=["risk_off"],
                    acceptance_criteria=AcceptanceCriteria(),
                )
            )
            event = WorkflowEvent(event_id="evt-3", event_type="context", symbol="BTC", timeframe="1m", context_tags=["risk_off"])
            decisions = engine.handle_event(event, train_period="2021-2023", test_period="2024")
            self.assertTrue(decisions[0].triggered)
            self.assertEqual(len(queue.list_optimization_requests()), 1)
            source = inspect.getsource(engine_module)
            self.assertNotIn("run_optimization_loop", source)


if __name__ == "__main__":
    unittest.main()
