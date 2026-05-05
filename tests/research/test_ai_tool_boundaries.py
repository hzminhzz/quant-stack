from __future__ import annotations

import inspect
import ast
import tempfile
import unittest
from pathlib import Path

from quant_stack.artifacts.store import load_artifact
from quant_stack.research.schemas import BacktestSummary
from quant_stack.research.tools import list_registered_strategies, request_backtest_from_plan, submit_experiment
import quant_stack.research.tools as tools
from tests.research.test_experiment_queue import valid_plan


class AIToolBoundaryTests(unittest.TestCase):
    def test_strategy_registry_access_is_read_only(self) -> None:
        self.assertIn("rsi_sma", list_registered_strategies())

    def test_submit_experiment_writes_queue_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_id = submit_experiment(valid_plan(), queue_path=Path(tmpdir) / "queue.json", created_by_agent="planner")

        self.assertTrue(experiment_id.startswith("exp-"))

    def test_request_backtest_from_plan_cannot_call_live_execution(self) -> None:
        summary = request_backtest_from_plan(valid_plan())

        self.assertIsInstance(summary, BacktestSummary)
        self.assertEqual(summary.strategy_name, "rsi_sma")
        loaded = load_artifact(BacktestSummary, summary.artifact_path)
        self.assertEqual(loaded.strategy_name, "rsi_sma")

    def test_ai_tools_do_not_import_broker_or_live_execution(self) -> None:
        source = inspect.getsource(tools)
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

        forbidden_modules = {"ccxt", "subprocess", "quant_stack.live.execution", "broker"}
        self.assertTrue(all(not name.startswith(tuple(forbidden_modules)) for name in imported))


if __name__ == "__main__":
    unittest.main()
