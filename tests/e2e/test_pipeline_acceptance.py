from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import polars as pl
import pytest

from scripts.run_pipeline_acceptance import run_acceptance
from quant_stack.research.optimization.acceptance_query import load_acceptance_query
from quant_stack.artifacts.store import load_artifact
from quant_stack.research.experiment_queue import OptimizationRequestRecord


class PipelineAcceptanceE2ETest(unittest.TestCase):
    def test_pipeline_acceptance_e2e(self) -> None:
        query_yaml = """
strategy_name: rsi_sma
symbol: BTC
timeframe: 1m
context_gate:
  max_spread_bps: 15.0
  required_context_tags: ["risk_off"]
artifact_mode: proposed_only
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            query_path = root / "query.yaml"
            query_path.write_text(query_yaml, encoding="utf-8")

            output_dir = root / "output"
            fixture_root = root / "fixtures"
            intelligence_root = root / "intelligence"

            query = load_acceptance_query(query_path)
            self.assertEqual(query.strategy_name, "rsi_sma")

            artifact_set = run_acceptance(
                query,
                output_dir=output_dir,
                fixture_root=fixture_root,
                intelligence_root=intelligence_root
            )

            self.assertTrue(output_dir.exists())
            self.assertTrue((output_dir / "acceptance_manifest.json").exists())
            self.assertTrue((output_dir / "baseline_backtest.json").exists())
            self.assertTrue((output_dir / "candidate_backtest.json").exists())
            self.assertTrue((output_dir / "ohlcv_snapshot.json").exists())
            self.assertTrue((output_dir / "joined_context_frame.json").exists())

            self.assertTrue(artifact_set.optimization_proposed)
            opt_request_path = artifact_set.optimization_request_path
            self.assertIsNotNone(opt_request_path)
            assert opt_request_path is not None
            opt_path = output_dir / opt_request_path
            self.assertTrue(opt_path.exists())
            
            opt_record = load_artifact(OptimizationRequestRecord, opt_path)
            self.assertEqual(opt_record.request.strategy_name, "rsi_sma")
            self.assertEqual(opt_record.request.context_filters["max_spread_bps"], 15.0)
            self.assertEqual(opt_record.status.value, "proposed")
            self.assertEqual(opt_record.request_id, "phase17-rsi_sma-btc-1m-proposed")

            baseline_summary = json.loads((output_dir / "baseline_backtest.json").read_text())
            candidate_summary = json.loads((output_dir / "candidate_backtest.json").read_text())
            manifest = json.loads((output_dir / "acceptance_manifest.json").read_text())
            self.assertEqual(manifest["output_dir"], ".")
            self.assertIsNone(manifest["timestamp"])
            self.assertEqual(manifest["optimization_request_path"], "proposed_optimization.json")
            self.assertEqual(manifest["ohlcv_snapshot_meta"]["artifact_path"], "btc_usdt_swap_1m_ohlcv.parquet")
            
            joined_data = json.loads((output_dir / "joined_context_frame.json").read_text())
            rows = joined_data["rows"]
            for row in rows:
                if row.get("context_timestamp") and row.get("timestamp"):
                    self.assertTrue(row["context_timestamp"] <= row["timestamp"], 
                                    f"Future leak: context {row['context_timestamp']} > bar {row['timestamp']}")

            self.assertGreater(baseline_summary["entry_count"], 0)
            self.assertGreater(baseline_summary["trade_count"], 0)
            self.assertIn("suppressed_entries", candidate_summary)
            self.assertGreater(candidate_summary["suppressed_entries"], 0)
            self.assertLess(candidate_summary["trade_count"], baseline_summary["trade_count"])
            self.assertGreater(artifact_set.joined_context_rows, 0)

    def test_pipeline_safety_constraints(self) -> None:
        import subprocess

        try:
            subprocess.check_call(
                ["grep", "-r", "import pandas", "quant_stack"],
                stdout=subprocess.DEVNULL
            )
            self.fail("Found pandas import in quant_stack")
        except subprocess.CalledProcessError:
            pass 

        script_path = "scripts/run_pipeline_acceptance.py"
        with open(script_path, "r") as f:
            content = f.read()
            for forbidden in ["broker", "live", "account"]:
                self.assertNotIn(f"import {forbidden}", content)
                self.assertNotIn(f"from {forbidden}", content)

    def test_no_lookahead_invariant(self) -> None:
        query_yaml = """
strategy_name: rsi_sma
symbol: BTC
timeframe: 1m
context_gate:
  max_spread_bps: 10.0
artifact_mode: proposed_only
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            query_path = root / "query.yaml"
            query_path.write_text(query_yaml, encoding="utf-8")
            output_dir = root / "output"
            
            query = load_acceptance_query(query_path)
            run_acceptance(
                query,
                output_dir=output_dir,
                fixture_root=root / "fixtures",
                intelligence_root=root / "intelligence"
            )

            joined_data = json.loads((output_dir / "joined_context_frame.json").read_text())
            rows = joined_data["rows"]
            
            prev_target = 0.0
            for row in rows:
                target = row.get("target_position", 0.0)
                pos = row.get("position", 0.0)
                self.assertEqual(pos, prev_target, f"Lookahead detected: pos {pos} != prev_target {prev_target}")
                prev_target = target


if __name__ == "__main__":
    unittest.main()
