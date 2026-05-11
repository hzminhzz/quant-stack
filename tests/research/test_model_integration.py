from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from quant_stack.research.model_integration import (
    AssetForecastResult,
    AssetWeightsResult,
    forecast_to_long_frame,
    forecast_to_signal_frame,
    run_research_model_backtest,
    weights_to_long_frame,
)


def _market_frame(symbol: str = "BTCUSDT") -> pl.DataFrame:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    close = [100.0, 101.0, 100.0, 102.0, 103.0]
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=i) for i in range(len(close))],
            "open": close,
            "high": [v + 0.5 for v in close],
            "low": [v - 0.5 for v in close],
            "close": close,
            "volume": [1.0] * len(close),
            "symbol": [symbol] * len(close),
            "timeframe": ["1m"] * len(close),
        }
    )


def test_forecast_shape_validation() -> None:
    with pytest.raises(ValueError, match="2D"):
        AssetForecastResult(expected_returns=np.array([1.0, 2.0]), timestamps=(), asset_ids=("BTCUSDT",))


def test_forecast_and_weight_long_frame_exports() -> None:
    ts = tuple(_market_frame()["timestamp"].to_list())
    forecast = AssetForecastResult(
        expected_returns=np.array([[0.1, -0.2], [0.2, 0.3], [0.0, 0.4], [0.1, np.nan], [0.5, 0.2]]),
        timestamps=ts,
        asset_ids=("BTCUSDT", "ETHUSDT"),
    )
    weights = AssetWeightsResult(
        weights=np.array([[0.7, 0.3], [0.6, 0.4], [0.5, 0.5], [0.55, 0.45], [0.65, 0.35]]),
        timestamps=ts,
        asset_ids=("BTCUSDT", "ETHUSDT"),
    )
    fdf = forecast_to_long_frame(forecast)
    wdf = weights_to_long_frame(weights)
    assert {"timestamp", "asset", "prediction_value"}.issubset(set(fdf.columns))
    assert {"timestamp", "asset", "weight", "selected"}.issubset(set(wdf.columns))
    assert fdf.height == 9  # one NaN skipped


def test_forecast_to_signal_frame_and_backtest_summary() -> None:
    market = _market_frame()
    ts = tuple(market["timestamp"].to_list())
    forecast = AssetForecastResult(
        expected_returns=np.array([[0.1], [-0.2], [0.3], [-0.1], [0.5]]),
        timestamps=ts,
        asset_ids=("BTCUSDT",),
    )
    signal_frame = forecast_to_signal_frame(market, forecast, symbol="BTCUSDT", threshold=0.0)
    assert "signal" in signal_frame.columns
    assert signal_frame["signal"].to_list() == [1.0, 0.0, 1.0, 0.0, 1.0]

    summary = run_research_model_backtest(
        market_frame=market,
        forecast=forecast,
        symbol="BTCUSDT",
        timeframe="1m",
        initial_capital=5000.0,
    )
    assert summary.strategy_name == "research_model_forecast"
    assert summary.symbol == "BTCUSDT"
    assert "cumulative_return" in summary.metrics
