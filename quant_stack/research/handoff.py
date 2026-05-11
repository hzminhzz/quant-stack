"""Research-layer model handoff helpers.

Borrowed abstraction pattern: keep a tiny, explicit contract for exporting model
outputs (predictions/weights) plus feed-spec metadata for downstream backtests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl


def resolve_feed_spec_mapping(
    frame: pl.DataFrame,
    *,
    timestamp_col: str = "timestamp",
    entity_col: str = "symbol",
    price_col: str = "close",
    prediction_col: str = "prediction_value",
    weight_col: str = "weight",
) -> dict[str, Any]:
    """Resolve a minimal feed-spec mapping from a frame schema."""
    columns = set(frame.columns)
    return {
        "timestamp_col": timestamp_col if timestamp_col in columns else "timestamp",
        "entity_col": entity_col if entity_col in columns else "symbol",
        "price_col": price_col if price_col in columns else "close",
        "prediction_col": prediction_col,
        "weight_col": weight_col,
        "columns": sorted(columns),
    }


def write_model_handoff_artifacts(
    *,
    output_dir: Path,
    predictions: pl.DataFrame | None = None,
    weights: pl.DataFrame | None = None,
    feed_spec: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Write model handoff artifacts for research-only integration trials."""
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}

    if predictions is not None:
        _require_columns(predictions, ["timestamp", "asset", "prediction_value"], context="predictions")
        pred_path = output_dir / "predictions.parquet"
        predictions.write_parquet(pred_path)
        artifacts["predictions.parquet"] = pred_path
    if weights is not None:
        _require_columns(weights, ["timestamp", "asset", "weight"], context="weights")
        weights_path = output_dir / "weights.parquet"
        weights.write_parquet(weights_path)
        artifacts["weights.parquet"] = weights_path

    if feed_spec is not None:
        spec_path = output_dir / "feed_spec.json"
        spec_path.write_text(json.dumps(feed_spec, indent=2), encoding="utf-8")
        artifacts["feed_spec.json"] = spec_path

    if metadata is not None:
        metadata_path = output_dir / "handoff_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        artifacts["handoff_metadata.json"] = metadata_path

    return artifacts


def _require_columns(df: pl.DataFrame, required: list[str], *, context: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{context} frame missing required column(s): {', '.join(missing)}")


__all__ = ["resolve_feed_spec_mapping", "write_model_handoff_artifacts"]
