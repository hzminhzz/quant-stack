from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

import duckdb
import numpy as np

from engine.evaluator import BacktestPhaseResult, CROPayload, DeterministicEvaluationResult, MonteCarloResult
from evolution.experience_pool import create_evolution_run, get_experience_by_id, initialize_experience_tables, update_evolution_run
from evolution.schemas import EvolutionRun
from live_swarm import AttemptOutcome, ExperienceLogger, _build_evaluation_summary
from strategy_families.base import StrategyProposal


def _build_mock_evaluation_result() -> DeterministicEvaluationResult:
    return DeterministicEvaluationResult(
        in_sample=BacktestPhaseResult(
            label="In-Sample",
            metrics={"cagr": 0.11, "smart_sharpe": 0.8},
            trades=np.asarray([1.0, -0.5, 0.25]),
        ),
        monte_carlo=MonteCarloResult(dd_95=-0.125, dd_50=-0.0825),
        out_of_sample=BacktestPhaseResult(
            label="Out-Of-Sample",
            metrics={"cagr": 0.04, "smart_sharpe": 0.5},
            trades=np.asarray([0.2, -0.1]),
        ),
        cro_payload=CROPayload(
            in_sample_metrics={"cagr": 0.11, "smart_sharpe": 0.8},
            in_sample_trade_count=3,
            out_of_sample_metrics={"cagr": 0.04, "smart_sharpe": 0.5},
            out_of_sample_trade_count=2,
            monte_carlo_95_dd_absolute_pct=12.5,
            note="ok",
        ),
    )


class LiveSwarmExperienceLoggingTests(unittest.TestCase):
    def test_update_evolution_run_persists_completion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            connection = duckdb.connect(str(Path(tmpdir) / "experience.duckdb"))
            self.addCleanup(connection.close)
            initialize_experience_tables(connection)

            run = EvolutionRun(
                run_id="run-202",
                objective="Track live swarm outcomes",
                strategy_type="bb",
                status="running",
                metadata={"asset": "ETH"},
            )
            create_evolution_run(connection, run)

            completed_run = run.model_copy(
                update={
                    "status": "completed",
                    "completed_at": run.created_at,
                    "metadata": {"asset": "ETH", "approved": True},
                }
            )
            update_evolution_run(connection, completed_run)

            row = connection.execute(
                "SELECT status, metadata_json FROM evolution_runs WHERE run_id = ?",
                [run.run_id],
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        status, metadata_json = row

        self.assertEqual(status, "completed")
        self.assertIsInstance(metadata_json, str)
        self.assertEqual(json.loads(metadata_json), {"asset": "ETH", "approved": True})

    def test_build_evaluation_summary_uses_structured_deterministic_result_fields(self) -> None:
        summary = _build_evaluation_summary(_build_mock_evaluation_result())

        self.assertEqual(summary["in_sample_trade_count"], 3)
        self.assertEqual(summary["out_of_sample_trade_count"], 2)
        self.assertEqual(summary["monte_carlo_95_dd_absolute_pct"], 12.5)
        self.assertEqual(summary["monte_carlo_median_dd_absolute_pct"], 8.25)

    def test_experience_logger_records_attempt_failure_and_final_run_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            connection = duckdb.connect(str(Path(tmpdir) / "experience.duckdb"))
            self.addCleanup(connection.close)
            initialize_experience_tables(connection)

            args = argparse.Namespace(
                asset="ETH",
                train_years=[2021, 2022, 2023],
                test_years=[2024],
                max_iterations=4,
                mc_seed=42,
                signal=False,
                artifact_path="artifacts/latest_validation.json",
            )
            logger = ExperienceLogger.create(connection, args, "bb")
            strategy = StrategyProposal(
                strategy_type="bb",
                params={"bb_length": 20, "bb_std": 2.0, "regime_sma": 200},
                rationale="Volatility breakout with trend filter",
            )

            experience_id = logger.record_attempt(
                iteration=0,
                strategy=strategy,
                outcome=AttemptOutcome.DETERMINISTIC_REJECTION,
                details={"evaluation_summary": {"deterministic_rejection": "Too few trades"}},
            )
            logger.record_failure(
                experience_id=experience_id,
                stage="deterministic_evaluation",
                failure_type="deterministic_rejection",
                message="Too few trades",
                details={"iteration": 1},
            )
            finalized_run = logger.finalize(
                status="failed",
                metadata_updates={"final_outcome": "swarm_exhausted", "approved": False},
            )

            restored_entry = get_experience_by_id(connection, experience_id)
            stored_run = connection.execute(
                "SELECT status, metadata_json FROM evolution_runs WHERE run_id = ?",
                [logger.run.run_id],
            ).fetchone()
            failure_row = connection.execute(
                "SELECT stage, failure_type, message FROM failure_events WHERE experience_id = ?",
                [experience_id],
            ).fetchone()

        self.assertIsNotNone(restored_entry)
        assert restored_entry is not None
        self.assertEqual(restored_entry.metrics["outcome"], "deterministic_rejection")
        self.assertEqual(
            restored_entry.artifacts["details"]["evaluation_summary"]["deterministic_rejection"],
            "Too few trades",
        )
        self.assertIsNotNone(stored_run)
        assert stored_run is not None
        self.assertIsInstance(stored_run[1], str)
        self.assertEqual(failure_row, ("deterministic_evaluation", "deterministic_rejection", "Too few trades"))
        self.assertEqual(stored_run[0], "failed")
        self.assertEqual(
            json.loads(stored_run[1]),
            {
                "asset": "ETH",
                "train_years": [2021, 2022, 2023],
                "test_years": [2024],
                "max_iterations": 4,
                "mc_seed": 42,
                "signal_seeded": False,
                "artifact_path": "artifacts/latest_validation.json",
                "final_outcome": "swarm_exhausted",
                "approved": False,
            },
        )
        self.assertEqual(finalized_run.status, "failed")


if __name__ == "__main__":
    unittest.main()
