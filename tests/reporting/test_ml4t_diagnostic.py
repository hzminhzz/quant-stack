from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import pytest

import polars as pl

from quant_stack.reporting.backtest_report import GateConfig, ReportPolicy, write_backtest_artifacts
from quant_stack.reporting.ml4t_diagnostic import (
    export_ml4t_diagnostic_artifacts,
    generate_ml4t_tearsheet,
    validate_ml4t_diagnostic_artifacts,
)


def _sample_result_frame() -> pl.DataFrame:
    start = datetime(2026, 1, 1, 0, 0, 0)
    timestamps = [start + timedelta(minutes=i) for i in range(5)]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "close": [100.0, 101.0, 102.0, 101.0, 103.0],
            "position": [0.0, 1.0, 1.0, 0.0, 1.0],
            "equity": [10000.0, 10020.0, 10030.0, 10010.0, 10050.0],
            "is_exposed": [False, True, True, False, True],
        }
    )


def test_export_ml4t_diagnostic_artifacts_writes_required_files(tmp_path: Path) -> None:
    frame = _sample_result_frame()
    trades = pl.DataFrame(
        {
            "entry_time": [frame["timestamp"][1]],
            "exit_time": [frame["timestamp"][3]],
            "entry_price": [101.0],
            "exit_price": [101.0],
            "pnl": [0.0],
        }
    )
    artifacts = export_ml4t_diagnostic_artifacts(
        result_frame=frame,
        output_dir=tmp_path,
        run_config={"strategy": "rsi_sma", "data_path": "btcusdt_1m.parquet", "initial_capital": 10000.0},
        trades_df=trades,
    )
    for filename in [
        "trades.parquet",
        "daily_returns.parquet",
        "equity.parquet",
        "weights.parquet",
        "portfolio_state.parquet",
        "fills.parquet",
        "spec.json",
    ]:
        assert filename in artifacts
        assert artifacts[filename].exists()

    daily = pl.read_parquet(tmp_path / "daily_returns.parquet")
    assert {"date", "daily_return"}.issubset(set(daily.columns))

    out_trades = pl.read_parquet(tmp_path / "trades.parquet")
    assert {
        "symbol",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "quantity",
        "pnl",
        "pnl_percent",
        "bars_held",
    }.issubset(set(out_trades.columns))


def test_write_backtest_artifacts_includes_ml4t_files(tmp_path: Path) -> None:
    frame = _sample_result_frame()
    artifacts = write_backtest_artifacts(
        result_frame=frame,
        metrics={"cumulative_return": 0.01, "max_drawdown": -0.02, "smart_sharpe": 1.0},
        run_config={"strategy": "rsi_sma", "data_path": "btc_1m.parquet", "initial_capital": 10000.0},
        output_dir=tmp_path,
        title="test",
        gate_config=GateConfig(report_policy=ReportPolicy.NEVER, min_trades=0),
    )
    assert "trades.parquet" in artifacts
    assert "daily_returns.parquet" in artifacts
    assert "weights.parquet" in artifacts
    assert "portfolio_state.parquet" in artifacts


def test_ml4t_export_handles_empty_trades_schema(tmp_path: Path) -> None:
    artifacts = export_ml4t_diagnostic_artifacts(
        result_frame=_sample_result_frame(),
        output_dir=tmp_path,
        run_config={"strategy": "rsi_sma", "data_path": "btc_1m.parquet", "initial_capital": 10000.0},
        trades_df=None,
    )
    trades = pl.read_parquet(artifacts["trades.parquet"])
    assert trades.height == 0
    assert trades.schema["entry_time"] == pl.Datetime("us")
    assert trades.schema["exit_time"] == pl.Datetime("us")
    assert trades.schema["bars_held"] == pl.Int64


def test_ml4t_export_daily_returns_are_daily_and_sorted(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, 23, 58, 0)
    timestamps = [start + timedelta(minutes=i) for i in range(6)]
    frame = pl.DataFrame(
        {
            "timestamp": timestamps,
            "close": [100.0, 100.5, 101.0, 101.5, 102.0, 103.0],
            "position": [0.0, 1.0, 1.0, 1.0, 0.0, 0.0],
            "equity": [10000.0, 10010.0, 10020.0, 10025.0, 10030.0, 10035.0],
            "is_exposed": [False, True, True, True, False, False],
        }
    )
    artifacts = export_ml4t_diagnostic_artifacts(
        result_frame=frame,
        output_dir=tmp_path,
        run_config={"strategy": "rsi_sma", "data_path": "btc_1m.parquet", "initial_capital": 10000.0},
        trades_df=None,
    )
    daily = pl.read_parquet(artifacts["daily_returns.parquet"])
    assert daily.columns == ["date", "daily_return"]
    assert daily["date"].is_sorted()
    assert daily.select(pl.col("date").n_unique()).item() == daily.height


def test_generate_tearsheet_raises_clear_error_without_ml4t(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import quant_stack.reporting.ml4t_diagnostic as module

    frame = _sample_result_frame()
    _ = export_ml4t_diagnostic_artifacts(
        result_frame=frame,
        output_dir=tmp_path,
        run_config={"strategy": "rsi_sma", "data_path": "btcusdt_1m.parquet", "initial_capital": 10000.0},
        trades_df=None,
    )

    def _boom(_: str):
        raise ImportError("missing")

    monkeypatch.setattr(module, "import_module", _boom)
    with pytest.raises(RuntimeError, match="ml4t-diagnostic is not installed"):
        generate_ml4t_tearsheet(artifact_dir=tmp_path)


def test_validate_ml4t_diagnostic_artifacts_checks_schema(tmp_path: Path) -> None:
    frame = _sample_result_frame()
    trades = pl.DataFrame(
        {
            "entry_time": [frame["timestamp"][1]],
            "exit_time": [frame["timestamp"][3]],
            "entry_price": [101.0],
            "exit_price": [101.0],
            "pnl": [0.0],
        }
    )
    _ = export_ml4t_diagnostic_artifacts(
        result_frame=frame,
        output_dir=tmp_path,
        run_config={"strategy": "rsi_sma", "data_path": "btcusdt_1m.parquet", "initial_capital": 10000.0},
        trades_df=trades,
    )
    validate_ml4t_diagnostic_artifacts(tmp_path)
