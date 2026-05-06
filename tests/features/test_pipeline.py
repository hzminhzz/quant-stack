from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest

from quant_stack.features.pipeline import build_feature_dataset
from quant_stack.features.schemas import FeaturePipelineConfig


def _frame(with_derivatives: bool) -> pl.DataFrame:
    n = 260
    base = {
        "timestamp": [datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc) + i * timedelta(minutes=1) for i in range(n)],
        "available_at": [datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc) + i * timedelta(minutes=1) for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "timeframe": ["1m"] * n,
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [10.0 + (i % 5) for i in range(n)],
        "turnover": [1000.0 + i for i in range(n)],
    }
    if with_derivatives:
        base["funding_rate"] = [0.0001 if i % 10 == 0 else 0.0 for i in range(n)]
        base["funding_available_at"] = base["available_at"]
        base["open_interest"] = [1000.0 + i for i in range(n)]
        base["oi_available_at"] = base["available_at"]
        base["basis"] = [0.001 if i % 7 == 0 else 0.0 for i in range(n)]
        base["basis_available_at"] = base["available_at"]
    return pl.DataFrame(base)


def test_pipeline_preserves_rows_and_order() -> None:
    df = _frame(with_derivatives=True)
    out = build_feature_dataset(df)
    assert out.height == df.height
    assert out["timestamp"].to_list() == df["timestamp"].to_list()
    for col in ["ret_1", "realized_vol_60", "rsi_14", "ema_200", "bb_pos_20", "volume_zscore_20", "funding_zscore_30", "forced_selling_proxy"]:
        assert col in out.columns


def test_pipeline_missing_derivatives_modes() -> None:
    df = _frame(with_derivatives=False)
    out = build_feature_dataset(df, config=FeaturePipelineConfig(allow_missing_derivatives=True))
    assert out.height == df.height

    with pytest.raises(ValueError):
        build_feature_dataset(df, config=FeaturePipelineConfig(allow_missing_derivatives=False))


def test_pipeline_enforce_single_symbol_timeframe_guard() -> None:
    df = _frame(with_derivatives=False)
    df = df.with_columns(pl.when(pl.arange(0, pl.len()) > 100).then(pl.lit("ETHUSDT")).otherwise(pl.col("symbol")).alias("symbol"))
    with pytest.raises(ValueError, match="panel detected"):
        build_feature_dataset(df, config=FeaturePipelineConfig(enforce_single_symbol=True, allow_panel=False))


def test_pipeline_enforce_single_timeframe_guard() -> None:
    df = _frame(with_derivatives=False)
    df = df.with_columns(pl.when(pl.arange(0, pl.len()) > 100).then(pl.lit("5m")).otherwise(pl.col("timeframe")).alias("timeframe"))
    with pytest.raises(ValueError, match="panel detected"):
        build_feature_dataset(df, config=FeaturePipelineConfig(enforce_single_symbol=True, allow_panel=False))


def test_pipeline_strict_derivative_causality_rejects_bad_availability() -> None:
    df = _frame(with_derivatives=True).with_columns(
        (pl.col("available_at") + pl.duration(minutes=1)).alias("funding_available_at")
    )
    with pytest.raises(ValueError, match="causality"):
        build_feature_dataset(df, config=FeaturePipelineConfig(strict_derivative_causality=True))


def test_pipeline_strict_derivative_requires_availability_columns() -> None:
    df = _frame(with_derivatives=True).drop("funding_available_at")
    with pytest.raises(ValueError, match="funding_available_at"):
        build_feature_dataset(df, config=FeaturePipelineConfig(strict_derivative_causality=True))


def test_pipeline_non_strict_derivative_allows_missing_availability() -> None:
    df = _frame(with_derivatives=True).drop("funding_available_at")
    out = build_feature_dataset(df, config=FeaturePipelineConfig(strict_derivative_causality=False))
    assert out.height == df.height


def test_no_pandas_import_in_features() -> None:
    import pathlib

    base = pathlib.Path("/root/quant-factory/quant_stack/features")
    offenders: list[str] = []
    for path in base.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import pandas" in text or "pd." in text:
            offenders.append(path.name)
    assert offenders == []
