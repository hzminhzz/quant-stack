from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from evolution.schemas import ResearchGuardCheck, ResearchGuardReport
from evolution.research_guard import guard_research_code
from pipeline_artifacts import load_research_artifact
from research import ResearchConfig, save_research_artifact_for_pipeline


VALID_POLARS_CODE = """
import polars as pl


def backtest_signal(df: pl.DataFrame) -> float:
    signal = df.with_columns(pl.col(\"close\").pct_change().fill_null(0.0).alias(\"ret\"))
    return float(signal.select(pl.col(\"ret\").sum()).item())
"""


class ResearchGuardTests(unittest.TestCase):
    def test_guard_accepts_required_backtest_signal_shape(self) -> None:
        report = guard_research_code(VALID_POLARS_CODE, strategy_type="rsi")

        self.assertTrue(report.passed)
        self.assertTrue(report.checks["required_function"].passed)
        self.assertTrue(report.checks["disallowed_patterns"].passed)
        self.assertTrue(report.checks["lookahead_bias"].passed)
        self.assertTrue(report.checks["ohlcv_boundary"].passed)
        self.assertTrue(report.checks["family_logic"].passed)

    def test_guard_rejects_missing_required_signature(self) -> None:
        report = guard_research_code(
            """
import polars as pl


def backtest_signal(df):
    return 1.0
""",
            strategy_type="rsi",
        )

        self.assertFalse(report.passed)
        self.assertFalse(report.checks["required_function"].passed)
        self.assertIn("def backtest_signal(df: pl.DataFrame) -> float", report.summary)

    def test_guard_rejects_hidden_data_loading_and_shell_patterns(self) -> None:
        report = guard_research_code(
            """
import polars as pl
import subprocess


def backtest_signal(df: pl.DataFrame) -> float:
    other = pl.read_parquet(\"hidden.parquet\")
    subprocess.run([\"sh\", \"-lc\", \"echo hi\"], check=True)
    return float(other.height)
""",
            strategy_type="rsi",
        )

        self.assertFalse(report.passed)
        self.assertFalse(report.checks["disallowed_patterns"].passed)
        self.assertIn("read_parquet", report.checks["disallowed_patterns"].detail)

    def test_guard_rejects_negative_shift_lookahead(self) -> None:
        report = guard_research_code(
            """
import polars as pl


def backtest_signal(df: pl.DataFrame) -> float:
    next_close = df.select(pl.col(\"close\").shift(-1).alias(\"next_close\"))
    return float(next_close.height)
""",
            strategy_type="rsi",
        )

        self.assertFalse(report.passed)
        self.assertFalse(report.checks["lookahead_bias"].passed)
        self.assertIn("negative shift", report.checks["lookahead_bias"].detail)

    def test_guard_rejects_non_ohlcv_column_references(self) -> None:
        report = guard_research_code(
            """
import polars as pl


def backtest_signal(df: pl.DataFrame) -> float:
    target = df.select(pl.col(\"target\").sum())
    return float(target.item())
""",
            strategy_type="rsi",
        )

        self.assertFalse(report.passed)
        self.assertFalse(report.checks["ohlcv_boundary"].passed)
        self.assertIn("target", report.checks["ohlcv_boundary"].detail)

    def test_guard_allows_alias_references_but_rejects_family_mismatch(self) -> None:
        report = guard_research_code(
            """
import polars as pl


def backtest_signal(df: pl.DataFrame) -> float:
    frame = df.with_columns([
        pl.col(\"close\").rolling_mean(20).alias(\"middle_band\"),
        pl.col(\"close\").pct_change().fill_null(0.0).alias(\"ret\"),
    ])
    return float(frame.select(pl.col(\"ret\").sum()).item())
""",
            strategy_type="rsi",
        )

        self.assertFalse(report.passed)
        self.assertTrue(report.checks["ohlcv_boundary"].passed)
        self.assertFalse(report.checks["family_logic"].passed)
        self.assertIn("middle_band", report.checks["family_logic"].detail)

    def test_research_artifact_persists_guard_report_additively(self) -> None:
        config = ResearchConfig(
            signal_artifact_path="unused",
            research_artifact_path="unused",
            data_path="unused",
            paper_sources="unused",
            paper_year=None,
            paper_max_results=1,
            skip_paper_search=True,
        )
        guard_report = ResearchGuardReport(
            passed=True,
            summary="ok",
            checks={
                "required_function": ResearchGuardCheck(passed=True, detail="matched signature"),
                "disallowed_patterns": ResearchGuardCheck(passed=True, detail="clear"),
                "lookahead_bias": ResearchGuardCheck(passed=True, detail="clear"),
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "research.json"
            config.research_artifact_path = str(path)

            save_research_artifact_for_pipeline(
                config,
                strategy_type="rsi",
                signal_data={"asset": "BTC"},
                paper_context="ctx",
                polars_code=VALID_POLARS_CODE,
                guard_report=guard_report,
            )
            artifact = load_research_artifact(path)

        self.assertIsNotNone(artifact.guard_report)
        assert artifact.guard_report is not None
        self.assertTrue(artifact.guard_report.passed)
        self.assertEqual(artifact.guard_report.summary, "ok")

    def test_main_stops_before_saving_when_guard_fails(self) -> None:
        config = ResearchConfig(
            signal_artifact_path="signal.json",
            research_artifact_path="research.json",
            data_path="market.parquet",
            paper_sources="crossref",
            paper_year=None,
            paper_max_results=1,
            skip_paper_search=True,
        )
        signal_artifact = MagicMock(strategy_type="rsi", signal={"asset": "BTC"})
        bad_code = """
import polars as pl


def backtest_signal(df: pl.DataFrame) -> float:
    return float(df.select(pl.col(\"close\").shift(-1).sum()).item())
"""

        with patch("research.parse_args", return_value=config), \
            patch("research.load_signal_for_research", return_value=signal_artifact), \
            patch("research.fetch_paper_context", return_value=("ctx", None)), \
            patch("research.print_paper_summary"), \
            patch("research.configure_dspy"), \
            patch("research.generate_polars_script", return_value=bad_code), \
            patch("research.save_research_artifact_for_pipeline") as save_mock, \
            patch("research.load_market_data") as load_market_data_mock:
            import research

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                research.main()

        self.assertIn("Research guard failed:", stdout.getvalue())
        save_mock.assert_not_called()
        load_market_data_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
