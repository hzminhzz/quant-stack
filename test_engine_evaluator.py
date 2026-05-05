from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl
from pydantic import BaseModel

from engine.evaluator import (
    BacktestPhaseResult,
    CROPayload,
    CROPayloadRequest,
    DeterministicEvaluationRequest,
    MarketFrameLoadRequest,
    MonteCarloResult,
    PhaseValidationRequest,
    build_cro_payload,
    evaluate_candidate,
    load_market_frames,
    validate_phase_metrics,
)
from strategy_families import get_strategy_family
from strategy_families.base import StrategyFamily


@dataclass
class _TestDeps:
    db: duckdb.DuckDBPyConnection


class _FakeParams(BaseModel):
    marker: int = 1


class _FakeFamily(StrategyFamily):
    name = "fake"
    raw_data_timeframe = "1m"
    validation_timeframe = "1m"

    def __init__(self, equity: np.ndarray, exposed: np.ndarray, trades: np.ndarray) -> None:
        self._equity = equity
        self._exposed = exposed
        self._trades = trades

    def build_initial_prompt(self, seed_info: str) -> str:
        return seed_info

    def build_retry_prompt(self, critique: str) -> str:
        return critique

    def build_seed_hint(self, signal: dict[str, Any]) -> str:
        return str(signal)

    def signal_model(self) -> type[BaseModel]:
        return _FakeParams

    def build_discovery_prompt(self, raw_markdown: str, paper_context: str) -> str:
        return raw_markdown + paper_context

    def build_paper_query(self, signal: dict[str, Any]) -> str:
        return str(signal)

    def validate_params(self, params: dict[str, Any]) -> BaseModel:
        return _FakeParams.model_validate(params)

    def prepare_market_data(self, raw_df: pl.DataFrame) -> pl.DataFrame:
        return raw_df.sort("timestamp")

    def simulate(self, close_prices, params: BaseModel):
        return self._equity, self._exposed, self._trades

    def format_params(self, params: BaseModel) -> str:
        return str(params)

    def build_execution_prompt(self, params: BaseModel, class_name: str) -> str:
        return class_name


class EvaluatorTests(unittest.TestCase):
    def test_build_cro_payload_converts_numpy_scalars_and_counts(self) -> None:
        in_sample = BacktestPhaseResult(
            label="In-Sample",
            metrics={"cagr": np.float64(0.12), "smart_sharpe": np.float32(0.8)},
            trades=np.array([0.01, -0.02, 0.03], dtype=np.float64),
        )
        out_of_sample = BacktestPhaseResult(
            label="Out-Of-Sample",
            metrics={"cagr": np.float64(-0.01), "max_drawdown": np.float64(-0.05)},
            trades=np.array([0.01], dtype=np.float64),
        )
        payload = build_cro_payload(
            CROPayloadRequest(
                in_sample=in_sample,
                out_of_sample=out_of_sample,
                monte_carlo=MonteCarloResult(dd_95=np.float64(-0.1234), dd_50=np.float64(-0.05)),
            )
        )

        self.assertIsInstance(payload, CROPayload)
        self.assertEqual(payload.in_sample_trade_count, 3)
        self.assertEqual(payload.out_of_sample_trade_count, 1)
        self.assertEqual(payload.monte_carlo_95_dd_absolute_pct, 12.34)
        self.assertEqual(payload.model_dump()["in_sample_metrics"]["cagr"], 0.12)
        self.assertEqual(payload.model_dump()["out_of_sample_metrics"]["max_drawdown"], -0.05)

    def test_load_market_frames_matches_family_preparation(self) -> None:
        family = get_strategy_family("bb")
        timestamps = pl.datetime_range(
            start=pl.datetime(2021, 1, 1, 0, 0, 0),
            end=pl.datetime(2021, 1, 1, 1, 59, 0),
            interval="1m",
            eager=True,
        )
        train_raw = pl.DataFrame(
            {
                "timestamp": (timestamps.dt.epoch(time_unit="ms")),
                "open": np.linspace(100.0, 101.0, len(timestamps)),
                "high": np.linspace(100.5, 101.5, len(timestamps)),
                "low": np.linspace(99.5, 100.5, len(timestamps)),
                "close": np.linspace(100.2, 101.2, len(timestamps)),
                "volume": np.ones(len(timestamps), dtype=np.float64),
            }
        )
        test_timestamps = timestamps.dt.offset_by("3y").dt.epoch(time_unit="ms")
        test_raw = train_raw.with_columns(pl.Series("timestamp", test_timestamps))

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "Data" / "Binance"
            data_dir.mkdir(parents=True)
            train_raw.write_parquet(data_dir / "ETH_1m_2021.parquet")
            test_raw.write_parquet(data_dir / "ETH_1m_2024.parquet")

            deps = _TestDeps(db=duckdb.connect())
            loaded = load_market_frames(
                deps=deps,
                family=family,
                request=MarketFrameLoadRequest(
                    asset="ETH",
                    train_years=[2021],
                    test_years=[2024],
                    data_dir=data_dir.as_posix(),
                ),
            )

        expected_train = family.prepare_market_data(train_raw.with_columns(pl.from_epoch("timestamp", time_unit="ms")))
        expected_test = family.prepare_market_data(test_raw.with_columns(pl.from_epoch("timestamp", time_unit="ms")))

        self.assertEqual(loaded.train_df.to_dict(as_series=False), expected_train.to_dict(as_series=False))
        self.assertEqual(loaded.test_df.to_dict(as_series=False), expected_test.to_dict(as_series=False))
        np.testing.assert_allclose(loaded.train_close, expected_train["close"].to_numpy())
        np.testing.assert_allclose(loaded.test_close, expected_test["close"].to_numpy())

    def test_evaluate_candidate_runs_phases_and_builds_payload(self) -> None:
        timestamps = pl.datetime_range(
            start=pl.datetime(2021, 1, 1, 0, 0, 0),
            end=pl.datetime(2021, 1, 5, 0, 0, 0),
            interval="1d",
            eager=True,
        )
        frame = pl.DataFrame(
            {
                "timestamp": timestamps,
                "close": [100.0, 101.0, 100.5, 102.0, 103.0],
            }
        )
        family = _FakeFamily(
            equity=np.array([1.0, 1.02, 1.01, 1.03, 1.04], dtype=np.float64),
            exposed=np.array([True, True, True, False, True], dtype=np.bool_),
            trades=np.array([0.02, -0.01, 0.03], dtype=np.float64),
        )

        result = evaluate_candidate(
            DeterministicEvaluationRequest(
                family=family,
                params=_FakeParams(),
                train_close=frame["close"].to_numpy(),
                train_df=frame,
                test_close=frame["close"].to_numpy(),
                test_df=frame,
                mc_seed=123,
            )
        )

        self.assertIsNone(result.deterministic_rejection)
        self.assertIsNotNone(result.monte_carlo)
        self.assertIsNotNone(result.out_of_sample)
        self.assertIsNotNone(result.cro_payload)
        out_of_sample = result.out_of_sample
        cro_payload = result.cro_payload
        assert out_of_sample is not None
        assert cro_payload is not None
        self.assertEqual(result.in_sample.label, "In-Sample")
        self.assertEqual(out_of_sample.label, "Out-Of-Sample")
        self.assertEqual(cro_payload.in_sample_trade_count, 3)
        self.assertGreater(result.in_sample.metrics["cagr"], 0.0)

    def test_evaluate_candidate_stops_before_monte_carlo_when_in_sample_fails_prop_validation(self) -> None:
        timestamps = pl.datetime_range(
            start=pl.datetime(2021, 1, 1, 0, 0, 0),
            end=pl.datetime(2021, 1, 5, 0, 0, 0),
            interval="1d",
            eager=True,
        )
        frame = pl.DataFrame(
            {
                "timestamp": timestamps,
                "close": [100.0, 99.0, 98.0, 97.0, 96.0],
            }
        )
        family = _FakeFamily(
            equity=np.array([1.0, 0.95, 0.90, 0.85, 0.80], dtype=np.float64),
            exposed=np.array([True, True, True, True, True], dtype=np.bool_),
            trades=np.array([-0.05, -0.06], dtype=np.float64),
        )

        result = evaluate_candidate(
            DeterministicEvaluationRequest(
                family=family,
                params=_FakeParams(),
                train_close=frame["close"].to_numpy(),
                train_df=frame,
                test_close=frame["close"].to_numpy(),
                test_df=frame,
                mc_seed=123,
            )
        )

        self.assertIsNotNone(result.deterministic_rejection)
        self.assertIsNone(result.monte_carlo)
        self.assertIsNone(result.out_of_sample)
        self.assertIsNone(result.cro_payload)
        deterministic_rejection = result.deterministic_rejection
        assert deterministic_rejection is not None
        self.assertIn("In-Sample failed deterministic prop-firm validation", deterministic_rejection)

    def test_evaluate_candidate_keeps_monte_carlo_when_oos_fails_prop_validation(self) -> None:
        timestamps = pl.datetime_range(
            start=pl.datetime(2021, 1, 1, 0, 0, 0),
            end=pl.datetime(2021, 1, 5, 0, 0, 0),
            interval="1d",
            eager=True,
        )
        train_frame = pl.DataFrame(
            {
                "timestamp": timestamps,
                "close": [100.0, 101.0, 100.5, 102.0, 103.0],
            }
        )
        test_frame = pl.DataFrame(
            {
                "timestamp": timestamps,
                "close": [100.0, 98.0, 96.0, 94.0, 92.0],
            }
        )

        class _SequentialFamily(_FakeFamily):
            def __init__(self) -> None:
                super().__init__(
                    equity=np.array([], dtype=np.float64),
                    exposed=np.array([], dtype=np.bool_),
                    trades=np.array([], dtype=np.float64),
                )
                self._calls = 0

            def simulate(self, close_prices, params: BaseModel):
                self._calls += 1
                if self._calls == 1:
                    return (
                        np.array([1.0, 1.02, 1.01, 1.03, 1.04], dtype=np.float64),
                        np.array([True, True, True, False, True], dtype=np.bool_),
                        np.array([0.02, -0.01, 0.03], dtype=np.float64),
                    )
                return (
                    np.array([1.0, 0.95, 0.90, 0.85, 0.80], dtype=np.float64),
                    np.array([True, True, True, True, True], dtype=np.bool_),
                    np.array([-0.05, -0.06], dtype=np.float64),
                )

        result = evaluate_candidate(
            DeterministicEvaluationRequest(
                family=_SequentialFamily(),
                params=_FakeParams(),
                train_close=train_frame["close"].to_numpy(),
                train_df=train_frame,
                test_close=test_frame["close"].to_numpy(),
                test_df=test_frame,
                mc_seed=123,
            )
        )

        self.assertIsNotNone(result.deterministic_rejection)
        self.assertIsNotNone(result.monte_carlo)
        self.assertIsNotNone(result.out_of_sample)
        self.assertIsNone(result.cro_payload)
        deterministic_rejection = result.deterministic_rejection
        assert deterministic_rejection is not None
        self.assertIn("Out-Of-Sample failed deterministic prop-firm validation", deterministic_rejection)

    def test_validate_phase_metrics_returns_typed_result(self) -> None:
        validation = validate_phase_metrics(
            PhaseValidationRequest(
                label="In-Sample",
                metrics={
                    "cumulative_return": 0.10,
                    "cagr": 0.12,
                    "time_in_market": 0.5,
                    "max_drawdown": -0.20,
                    "max_daily_drawdown": -0.02,
                    "max_consecutive_losing_days": 3,
                    "smart_sharpe": 0.8,
                    "smart_sortino": 1.0,
                    "tail_ratio": 1.1,
                    "gain_pain_ratio": 1.2,
                    "kelly_criterion": 0.1,
                },
            )
        )

        self.assertEqual(validation.label, "In-Sample")
        self.assertIsNotNone(validation.rejection_reason)
        rejection_reason = validation.rejection_reason
        assert rejection_reason is not None
        self.assertIn("deterministic prop-firm validation", rejection_reason)


if __name__ == "__main__":
    unittest.main()
