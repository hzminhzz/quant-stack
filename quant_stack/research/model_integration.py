"""Research-only model pipeline adapters.

This module mirrors a minimal subset of ml4t/models integration patterns:
- typed model outputs (forecast/weights)
- conversion to long frames
- conversion to quant_stack backtest signal frames

It must remain outside deterministic core execution modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.research.handoff import resolve_feed_spec_mapping, write_model_handoff_artifacts
from quant_stack.research.schemas import BacktestSummary


@dataclass(frozen=True)
class AssetForecastResult:
    expected_returns: np.ndarray
    timestamps: tuple[Any, ...]
    asset_ids: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        arr = np.asarray(self.expected_returns, dtype=float)
        if arr.ndim != 2:
            raise ValueError("expected_returns must be 2D [time, asset]")
        if self.timestamps and arr.shape[0] != len(self.timestamps):
            raise ValueError("timestamps length must match expected_returns time dimension")
        if self.asset_ids and arr.shape[1] != len(self.asset_ids):
            raise ValueError("asset_ids length must match expected_returns asset dimension")


@dataclass(frozen=True)
class AssetWeightsResult:
    weights: np.ndarray
    timestamps: tuple[Any, ...]
    asset_ids: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        arr = np.asarray(self.weights, dtype=float)
        if arr.ndim != 2:
            raise ValueError("weights must be 2D [time, asset]")
        if self.timestamps and arr.shape[0] != len(self.timestamps):
            raise ValueError("timestamps length must match weights time dimension")
        if self.asset_ids and arr.shape[1] != len(self.asset_ids):
            raise ValueError("asset_ids length must match weights asset dimension")


def forecast_to_long_frame(result: AssetForecastResult) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    arr = np.asarray(result.expected_returns, dtype=float)
    ts_values = result.timestamps or tuple(range(arr.shape[0]))
    assets = result.asset_ids or tuple(f"asset_{i}" for i in range(arr.shape[1]))

    for i, ts in enumerate(ts_values):
        for j, asset in enumerate(assets):
            value = float(arr[i, j])
            if not np.isfinite(value):
                continue
            rows.append({"timestamp": ts, "asset": asset, "prediction_value": value})
    return pl.DataFrame(rows)


def weights_to_long_frame(result: AssetWeightsResult, *, selected_threshold: float = 1e-9) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    arr = np.asarray(result.weights, dtype=float)
    ts_values = result.timestamps or tuple(range(arr.shape[0]))
    assets = result.asset_ids or tuple(f"asset_{i}" for i in range(arr.shape[1]))

    for i, ts in enumerate(ts_values):
        for j, asset in enumerate(assets):
            value = float(arr[i, j])
            if not np.isfinite(value):
                continue
            rows.append(
                {
                    "timestamp": ts,
                    "asset": asset,
                    "weight": value,
                    "selected": abs(value) > selected_threshold,
                }
            )
    return pl.DataFrame(rows)


def forecast_to_signal_frame(
    market_frame: pl.DataFrame,
    forecast: AssetForecastResult,
    *,
    symbol: str,
    threshold: float = 0.0,
) -> pl.DataFrame:
    """Map model forecasts to quant_stack signal frame for backtesting.

    Output includes canonical backtest columns and a `signal` in [0, 1].
    """
    if symbol not in set(forecast.asset_ids):
        raise ValueError(f"symbol '{symbol}' not found in forecast asset_ids")

    long_df = forecast_to_long_frame(forecast)
    asset_df = long_df.filter(pl.col("asset") == symbol).select(["timestamp", "prediction_value"])

    frame = market_frame.join(asset_df, on="timestamp", how="left")
    frame = frame.with_columns(pl.col("prediction_value").fill_null(0.0))
    frame = frame.with_columns((pl.col("prediction_value") > threshold).cast(pl.Float64).alias("signal"))
    return frame


def run_research_model_backtest(
    *,
    market_frame: pl.DataFrame,
    forecast: AssetForecastResult,
    symbol: str,
    timeframe: str,
    threshold: float = 0.0,
    initial_capital: float = 10_000.0,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> BacktestSummary:
    signal_frame = forecast_to_signal_frame(market_frame, forecast, symbol=symbol, threshold=threshold)
    result = PolarsSignalBacktester(
        initial_capital=initial_capital,
        cost_model=CostModel(fee_rate=fee_bps / 10_000.0, slippage_rate=slippage_bps / 10_000.0),
    ).run(signal_frame)
    return BacktestSummary(
        strategy_name="research_model_forecast",
        symbol=symbol,
        timeframe=timeframe,
        metrics=result.metrics,
        major_weaknesses=[],
        pass_fail="pass",
        artifact_path="",
    )


def export_forecast_handoff_artifacts(
    *,
    market_frame: pl.DataFrame,
    forecast: AssetForecastResult,
    output_dir: str,
    symbol: str,
    threshold: float = 0.0,
) -> dict[str, str]:
    """Export prediction + feed-spec artifacts for research backtest handoff."""
    predictions = forecast_to_long_frame(forecast)
    signal_frame = forecast_to_signal_frame(market_frame, forecast, symbol=symbol, threshold=threshold)
    feed_spec = resolve_feed_spec_mapping(signal_frame)
    artifacts = write_model_handoff_artifacts(
        output_dir=Path(output_dir),
        predictions=predictions,
        feed_spec=feed_spec,
        metadata={"symbol": symbol, "threshold": threshold, **forecast.metadata},
    )
    return {name: path.as_posix() for name, path in artifacts.items()}


__all__ = [
    "AssetForecastResult",
    "AssetWeightsResult",
    "forecast_to_long_frame",
    "weights_to_long_frame",
    "forecast_to_signal_frame",
    "run_research_model_backtest",
    "export_forecast_handoff_artifacts",
]
