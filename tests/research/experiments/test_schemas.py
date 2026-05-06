from __future__ import annotations

from datetime import datetime

import pytest

from quant_stack.research.experiments.schemas import ExperimentConfig


def test_experiment_config_validates() -> None:
    config = ExperimentConfig(
        strategy_name="forced_flow_band_reclaim",
        dataset_path="data.parquet",
        symbol="BTCUSDT",
        timeframe="1m",
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 2),
        output_dir="artifacts/research/experiments",
    )
    assert config.strategy_name == "forced_flow_band_reclaim"


def test_experiment_config_rejects_invalid_date_window() -> None:
    with pytest.raises(ValueError):
        ExperimentConfig(
            strategy_name="forced_flow_band_reclaim",
            dataset_path="data.parquet",
            symbol="BTCUSDT",
            timeframe="1m",
            start=datetime(2024, 1, 2),
            end=datetime(2024, 1, 1),
            output_dir="artifacts/research/experiments",
        )


def test_experiment_config_walk_forward_requires_bars() -> None:
    with pytest.raises(ValueError):
        ExperimentConfig(
            strategy_name="forced_flow_band_reclaim",
            dataset_path="data.parquet",
            symbol="BTCUSDT",
            timeframe="1m",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
            walk_forward_enabled=True,
            output_dir="artifacts/research/experiments",
        )


def test_experiment_config_rejects_partial_split_fields() -> None:
    with pytest.raises(ValueError, match="requires all fields"):
        ExperimentConfig(
            strategy_name="forced_flow_band_reclaim",
            dataset_path="data.parquet",
            symbol="BTCUSDT",
            timeframe="1m",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
            train_start=datetime(2024, 1, 1),
            output_dir="artifacts/research/experiments",
        )


def test_experiment_config_rejects_overlapping_train_test() -> None:
    with pytest.raises(ValueError, match="train_end must be <= test_start"):
        ExperimentConfig(
            strategy_name="forced_flow_band_reclaim",
            dataset_path="data.parquet",
            symbol="BTCUSDT",
            timeframe="1m",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
            train_start=datetime(2024, 1, 1, 0, 0),
            train_end=datetime(2024, 1, 1, 1, 0),
            test_start=datetime(2024, 1, 1, 0, 30),
            test_end=datetime(2024, 1, 1, 2, 0),
            output_dir="artifacts/research/experiments",
        )
