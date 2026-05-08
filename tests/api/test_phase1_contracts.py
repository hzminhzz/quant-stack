from __future__ import annotations

import polars as pl
import pytest

import quant_stack.api as api
from quant_stack.backtesting.results import BacktestResult


def test_backtest_request_defaults() -> None:
    request = api.BacktestRequest(strategy="rsi_sma", data_path="data/btc_1m.parquet")
    assert request.engine == "auto"
    assert request.output_mode == "summary"
    assert request.initial_capital == 10000.0


def test_validate_market_frame_normalizes_and_sorts() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [2_000, 1_000],
            "open": [1.0, 1.0],
            "high": [1.2, 1.2],
            "low": [0.9, 0.9],
            "close": [1.1, 1.1],
            "volume": [10.0, 5.0],
        }
    )
    normalized = api.validate_market_frame(frame)
    assert normalized["timestamp"].to_list()[0] < normalized["timestamp"].to_list()[1]


def test_to_backtest_summary_filters_non_numeric_metrics() -> None:
    artifact = api.BacktestArtifact(
        run_id="run_1",
        metrics_path="artifacts/run_1/metrics.json",
        summary_path="artifacts/run_1/summary.json",
    )
    summary = api.to_backtest_summary(
        run_id="run_1",
        strategy="rsi_sma",
        timeframe="1m",
        rows=100,
        metrics={"cagr": 0.12, "trades": 5, "note": "drop-me"},
        artifact_refs=artifact,
    )
    assert isinstance(summary, api.BacktestSummary)
    assert summary.metrics["cagr"] == pytest.approx(0.12)
    assert summary.metrics["trades"] == 5
    assert "note" not in summary.metrics


def test_backtest_result_keeps_internal_frame() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [1],
            "equity": [1.0],
            "is_exposed": [False],
        }
    )
    result = BacktestResult(frame=frame, metrics={}, trades=[])
    assert result.frame.shape == (1, 3)
