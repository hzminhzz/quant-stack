from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from quant_stack.api.tools import artifact_fetch_summary, backtest_batch, backtest_run, strategy_describe, strategy_list


def _make_dataset(path: Path, n: int = 200) -> None:
    ts = np.datetime64("2026-01-01T00:00:00") + np.arange(0, n * 60 * 1000, 60 * 1000, dtype="timedelta64[ms]")
    close = 100.0 + np.sin(np.linspace(0.0, 8.0, n)) * 3.0 + np.linspace(0.0, 1.0, n)
    frame = pl.DataFrame(
        {
            "timestamp": ts,
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )
    frame.write_parquet(path)


def test_strategy_tools_expose_registered_metadata() -> None:
    names = strategy_list()
    assert "rsi_sma" in names

    meta = strategy_describe("rsi_sma")
    assert meta["name"] == "rsi_sma"
    assert "params_schema" in meta
    assert "capabilities" in meta


def test_backtest_run_returns_summary_and_artifacts(tmp_path: Path) -> None:
    data_path = tmp_path / "sample.parquet"
    _make_dataset(data_path)

    payload = {
        "strategy": "rsi_sma",
        "data_path": str(data_path),
        "params": {"short_sma": 20, "long_sma": 100, "rsi_period": 14, "rsi_threshold": 35.0, "rsi_side": "below"},
        "engine": "polars",
        "output_mode": "summary",
    }
    summary = backtest_run(payload)
    assert summary["status"] == "ok"
    assert summary["strategy"] == "rsi_sma"
    assert summary["rows"] > 0
    assert Path(summary["artifact_refs"]["metrics_path"]).exists()


def test_backtest_batch_returns_top_results(tmp_path: Path) -> None:
    data_path = tmp_path / "sample_batch.parquet"
    _make_dataset(data_path, n=240)

    payload = {
        "strategy": "rsi_sma",
        "data_path": str(data_path),
        "param_matrix": [
            {"short_sma": 20, "long_sma": 100, "rsi_period": 10, "rsi_threshold": 35.0, "rsi_side": "below"},
            {"short_sma": 25, "long_sma": 120, "rsi_period": 14, "rsi_threshold": 40.0, "rsi_side": "below"},
        ],
        "top_n": 1,
    }
    batch = backtest_batch(payload)
    assert batch["total_candidates"] == 2
    assert batch["completed_candidates"] >= 1
    assert len(batch["top_results"]) == 1


def test_artifact_fetch_summary_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    payload = {"cumulative_return": 0.12, "smart_sharpe": 1.1}
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = artifact_fetch_summary(str(path))
    assert loaded == payload
