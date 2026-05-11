from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from quant_stack.research.handoff import resolve_feed_spec_mapping, write_model_handoff_artifacts


def test_resolve_feed_spec_mapping_uses_frame_columns() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [1, 2],
            "symbol": ["BTCUSDT", "BTCUSDT"],
            "close": [100.0, 101.0],
            "signal": [0.0, 1.0],
        }
    )
    spec = resolve_feed_spec_mapping(frame)
    assert spec["timestamp_col"] == "timestamp"
    assert spec["entity_col"] == "symbol"
    assert spec["price_col"] == "close"


def test_write_model_handoff_artifacts_writes_expected_files(tmp_path: Path) -> None:
    predictions = pl.DataFrame(
        {
            "timestamp": [1, 2],
            "asset": ["BTCUSDT", "BTCUSDT"],
            "prediction_value": [0.1, -0.2],
        }
    )
    artifacts = write_model_handoff_artifacts(
        output_dir=tmp_path,
        predictions=predictions,
        feed_spec={"timestamp_col": "timestamp"},
        metadata={"model": "trial"},
    )
    assert (tmp_path / "predictions.parquet").exists()
    assert (tmp_path / "feed_spec.json").exists()
    assert (tmp_path / "handoff_metadata.json").exists()
    assert "predictions.parquet" in artifacts


def test_write_model_handoff_artifacts_validates_required_columns(tmp_path: Path) -> None:
    bad_predictions = pl.DataFrame({"timestamp": [1], "asset": ["BTCUSDT"]})
    with pytest.raises(ValueError, match="prediction_value"):
        write_model_handoff_artifacts(output_dir=tmp_path, predictions=bad_predictions)
