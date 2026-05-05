from __future__ import annotations

import unittest

from quant_stack.research.optimization.schemas import AcceptanceCriteria
from quant_stack.workflows.schemas import WorkflowDefinition, WorkflowEvent
from quant_stack.workflows.triggers import ContextTagTrigger


class TriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = WorkflowDefinition(
            workflow_id="wf-1",
            strategy_name="rsi_sma",
            symbols=["BTC"],
            timeframes=["1m"],
            required_context_tags=["risk_off", "funding_extreme"],
            acceptance_criteria=AcceptanceCriteria(),
        )

    def test_trigger_fires_on_matching_tags(self) -> None:
        event = WorkflowEvent(event_id="evt-1", event_type="context", symbol="BTC", timeframe="1m", context_tags=["risk_off", "funding_extreme"])
        self.assertTrue(ContextTagTrigger().should_fire(self.definition, event))

    def test_trigger_does_not_fire_on_missing_tags(self) -> None:
        event = WorkflowEvent(event_id="evt-2", event_type="context", symbol="BTC", timeframe="1m", context_tags=["risk_off"])
        self.assertFalse(ContextTagTrigger().should_fire(self.definition, event))


if __name__ == "__main__":
    unittest.main()
