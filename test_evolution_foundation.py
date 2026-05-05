from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import duckdb

from engine.deps import QuantFactoryDeps
from pipeline_artifacts import (
    ResearchArtifact,
    SignalArtifact,
    ValidationArtifact,
    load_research_artifact,
    load_signal_artifact,
    load_validation_artifact,
    save_research_artifact,
    save_signal_artifact,
    save_validation_artifact,
)
from evolution.experience_pool import (
    create_evolution_run,
    get_experience_by_id,
    initialize_experience_tables,
    insert_experience_entry,
    insert_failure_event,
    list_run_experiences,
)
from evolution.schemas import BiasCheckReport, EvolutionRun, ExperienceEntry, FailureEvent


class EvolutionFoundationTests(unittest.TestCase):
    def test_pipeline_artifacts_roundtrip_optional_evolution_run_metadata(self) -> None:
        run = EvolutionRun(
            run_id="run-001",
            objective="Improve validation robustness",
            strategy_type="rsi",
            status="running",
        )
        signal_artifact = SignalArtifact(
            strategy_type="rsi",
            signal={"asset": "BTC", "params": {"short_sma": 20, "long_sma": 50}},
            source="paper.html",
            paper_context="ctx",
            evolution_run=run,
        )
        research_artifact = ResearchArtifact(
            strategy_type="rsi",
            signal=signal_artifact.signal,
            paper_context="ctx",
            polars_code="def backtest_signal(...): pass",
            evolution_run=run,
        )
        validation_artifact = ValidationArtifact(
            strategy_type="rsi",
            params={"short_sma": 20, "long_sma": 50},
            rationale="ok",
            in_sample_metrics={"cagr": 0.1},
            in_sample_trade_count=10,
            out_of_sample_metrics={"cagr": 0.05},
            out_of_sample_trade_count=5,
            monte_carlo_95_dd_absolute_pct=12.5,
            monte_carlo_median_dd_absolute_pct=8.0,
            approved=True,
            critique="ok",
            evolution_run=run,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            signal_path = Path(tmpdir) / "signal.json"
            research_path = Path(tmpdir) / "research.json"
            validation_path = Path(tmpdir) / "validation.json"

            save_signal_artifact(signal_artifact, signal_path)
            save_research_artifact(research_artifact, research_path)
            save_validation_artifact(validation_artifact, validation_path)

            loaded_signal = load_signal_artifact(signal_path)
            loaded_research = load_research_artifact(research_path)
            loaded_validation = load_validation_artifact(validation_path)

        self.assertEqual(loaded_signal.evolution_run.run_id, "run-001")
        self.assertEqual(loaded_research.evolution_run.objective, "Improve validation robustness")
        self.assertEqual(loaded_validation.evolution_run.status, "running")

    def test_experience_entry_model_roundtrip_preserves_nested_bias_report(self) -> None:
        entry = ExperienceEntry(
            experience_id="exp-001",
            run_id="run-001",
            strategy_type="rsi",
            candidate_name="candidate-a",
            hypothesis="Buy RSI dips after trend confirmation",
            metrics={"cagr": 0.12, "max_drawdown": -0.09},
            bias_check=BiasCheckReport(
                passed=True,
                summary="No obvious data leakage",
                checks={"lookahead": "clear", "survivorship": "clear"},
            ),
            artifacts={"validation_path": "artifacts/latest_validation.json"},
            notes="Promising baseline",
        )

        restored = ExperienceEntry.model_validate(entry.model_dump())

        self.assertEqual(restored.experience_id, "exp-001")
        self.assertTrue(restored.bias_check.passed)
        self.assertEqual(restored.bias_check.checks["lookahead"], "clear")

    def test_experience_pool_crud_roundtrip_uses_temp_duckdb_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "experience.duckdb"
            connection = duckdb.connect(str(db_path))
            self.addCleanup(connection.close)

            initialize_experience_tables(connection)

            run = EvolutionRun(
                run_id="run-101",
                objective="Improve out-of-sample CAGR",
                strategy_type="bb",
                status="running",
            )
            create_evolution_run(connection, run)

            entry = ExperienceEntry(
                experience_id="exp-101",
                run_id="run-101",
                strategy_type="bb",
                candidate_name="candidate-b",
                hypothesis="Tighten volatility breakout filters",
                metrics={"cagr": 0.08, "max_drawdown": -0.07},
                bias_check=BiasCheckReport(
                    passed=False,
                    summary="Potential lookahead bias",
                    checks={"lookahead": "investigate"},
                ),
                artifacts={"research_path": "artifacts/latest_research.json"},
            )
            insert_experience_entry(connection, entry)

            event = FailureEvent(
                event_id="fail-101",
                run_id="run-101",
                experience_id="exp-101",
                stage="validation",
                failure_type="bias_check_failed",
                message="Potential lookahead bias detected",
                details={"check": "lookahead"},
            )
            insert_failure_event(connection, event)

            restored_entry = get_experience_by_id(connection, "exp-101")
            run_entries = list_run_experiences(connection, "run-101")
            failure_count = connection.execute("SELECT COUNT(*) FROM failure_events WHERE run_id = ?", ["run-101"]).fetchone()[0]

        self.assertIsNotNone(restored_entry)
        assert restored_entry is not None
        self.assertEqual(restored_entry.strategy_type, "bb")
        self.assertFalse(restored_entry.bias_check.passed)
        self.assertEqual(restored_entry.created_at, entry.created_at)
        self.assertEqual(len(run_entries), 1)
        self.assertEqual(run_entries[0].experience_id, "exp-101")
        self.assertEqual(failure_count, 1)

    def test_load_multi_year_rejects_invalid_asset_and_year_inputs(self) -> None:
        deps = QuantFactoryDeps(db=MagicMock(), exchange=MagicMock())

        with self.assertRaises(ValueError):
            deps.load_multi_year(asset="ETH'); DROP TABLE evolution_runs; --")

        with self.assertRaises(ValueError):
            deps.load_multi_year(years=[2024, "2025"])


if __name__ == "__main__":
    unittest.main()
