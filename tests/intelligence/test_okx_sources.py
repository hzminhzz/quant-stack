from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from pathlib import Path

import polars as pl

from quant_stack.intelligence.sources.liquidations import liquidation_events_from_rows, load_liquidation_rows
import quant_stack.intelligence as intelligence_pkg


class OkxSourcesTests(unittest.TestCase):
    def test_liquidation_loader_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "liquidations.csv"
            pl.DataFrame(
                {
                    "symbol": ["BTC-USDT"],
                    "timestamp": [1704067200000],
                    "long_liquidation_notional": [250.0],
                    "short_liquidation_notional": [50.0],
                }
            ).write_csv(path)
            rows = load_liquidation_rows(path)
            events = liquidation_events_from_rows(rows)
            self.assertEqual(len(events), 1)

    def test_no_live_broker_account_imports(self) -> None:
        source = inspect.getsource(intelligence_pkg)
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        forbidden_prefixes = ("ccxt", "quant_stack.live", "broker", "quant_stack.live.execution")
        self.assertTrue(all(not module.startswith(forbidden_prefixes) for module in imported))


if __name__ == "__main__":
    unittest.main()
