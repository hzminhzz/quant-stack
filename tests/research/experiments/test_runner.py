from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from quant_stack.research.experiments.schemas import ExperimentConfig
from quant_stack.research.experiments.runner import run_strategy_experiment


def _dataset(path: str) -> None:
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 0, 0, 0),
        end=pl.datetime(2024, 1, 1, 0, 9, 0),
        interval="1m",
        eager=True,
    )
    frame = pl.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["BTCUSDT"] * len(timestamps),
            "timeframe": ["1m"] * len(timestamps),
            "open": [100.0 + i for i in range(len(timestamps))],
            "high": [100.5 + i for i in range(len(timestamps))],
            "low": [99.5 + i for i in range(len(timestamps))],
            "close": [100.0, 99.0, 98.0, 101.0, 102.0, 100.0, 99.0, 103.0, 104.0, 105.0],
            "volume": [10.0] * len(timestamps),
            "bb_mid_20": [100.0] * len(timestamps),
            "bb_lower_20": [98.0] * len(timestamps),
            "bb_reclaim_lower": [False, False, True, False, False, False, True, False, False, False],
            "bb_reclaim_lower_strict": [False, False, True, False, False, False, True, False, False, False],
            "liquidation_proxy_long": [False, False, True, False, False, False, True, False, False, False],
            "forced_selling_proxy": [False, False, True, False, False, False, True, False, False, False],
            "oi_flush": [False, False, True, False, False, False, True, False, False, False],
            "funding_zscore_30": [-0.2, -0.3, -2.0, -0.1, 0.2, -0.4, -1.8, -0.1, 0.2, 0.1],
            "basis_zscore_60": [-0.2, -0.3, -1.2, -0.1, 0.2, -0.4, -1.1, -0.1, 0.2, 0.1],
        }
    )
    frame.write_parquet(path)


def test_runner_loads_dataset_and_runs_experiment(tmp_path) -> None:
    dataset_path = (tmp_path / "features.parquet").as_posix()
    _dataset(dataset_path)

    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    report = run_strategy_experiment(config)

    assert report.strategy_name == "forced_flow_band_reclaim"
    assert report.baseline_result.mode == "baseline"
    assert report.context_result.mode == "context"
    assert (tmp_path / "out" / "comparison_report.md").exists()


def test_runner_missing_strategy_raises(tmp_path) -> None:
    dataset_path = (tmp_path / "features.parquet").as_posix()
    _dataset(dataset_path)

    config = ExperimentConfig(
        strategy_name="does_not_exist",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    with pytest.raises(ValueError, match="strategy not registered"):
        run_strategy_experiment(config)


def test_runner_missing_dataset_raises(tmp_path) -> None:
    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path=(tmp_path / "missing.parquet").as_posix(),
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    with pytest.raises(ValueError, match="dataset path does not exist"):
        run_strategy_experiment(config)


def test_runner_missing_required_dataset_columns_raises(tmp_path) -> None:
    dataset_path = (tmp_path / "bad.parquet").as_posix()
    pl.DataFrame({"timestamp": [datetime(2024, 1, 1)], "close": [100.0]}).write_parquet(dataset_path)
    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=1),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    with pytest.raises(ValueError, match=r"dataset missing required column\(s\)"):
        run_strategy_experiment(config)


def test_runner_rejects_path_dependent_strategy(tmp_path) -> None:
    dataset_path = (tmp_path / "features.parquet").as_posix()
    _dataset(dataset_path)
    config = ExperimentConfig(
        strategy_name="grid",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    with pytest.raises(ValueError, match="strategy not eligible"):
        run_strategy_experiment(config)


def test_runner_supports_explicit_train_test_split(tmp_path) -> None:
    dataset_path = (tmp_path / "features.parquet").as_posix()
    _dataset(dataset_path)
    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        train_start=datetime(2024, 1, 1),
        train_end=datetime(2024, 1, 1) + timedelta(minutes=5),
        test_start=datetime(2024, 1, 1) + timedelta(minutes=5),
        test_end=datetime(2024, 1, 1) + timedelta(minutes=9),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    report = run_strategy_experiment(config)
    assert report.baseline_result.backtest_result["rows"] > 0
    assert report.context_result.backtest_result["rows"] > 0
    assert report.baseline_result.backtest_result["rows"] == 5
    assert report.context_result.backtest_result["rows"] == 5


def test_runner_walk_forward_segmentation(tmp_path) -> None:
    dataset_path = (tmp_path / "features.parquet").as_posix()
    _dataset(dataset_path)
    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        walk_forward_enabled=True,
        walk_forward_train_bars=4,
        walk_forward_test_bars=2,
        walk_forward_step_bars=2,
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    report = run_strategy_experiment(config)
    segments = report.baseline_result.backtest_result.get("segments", [])
    assert len(segments) == 6
    assert sum(1 for segment in segments if segment["role"] == "test") == 3
    assert report.baseline_result.backtest_result["rows"] == 6


def test_mode_params_toggle_context_filter(tmp_path) -> None:
    dataset_path = (tmp_path / "features.parquet").as_posix()
    _dataset(dataset_path)

    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path=dataset_path,
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 1) + timedelta(minutes=9),
        initial_cash=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        output_dir=(tmp_path / "out").as_posix(),
    )
    report = run_strategy_experiment(config)

    assert report.baseline_result.params.get("use_context_filters") is False
    assert report.context_result.params.get("use_context_filters") is True
