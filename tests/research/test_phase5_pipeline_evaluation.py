from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl

from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.reporting.backtest_report import GateConfig, ReportPolicy, write_backtest_artifacts
from quant_stack.reporting.ml4t_diagnostic import validate_ml4t_diagnostic_artifacts
from quant_stack.research.model_integration import AssetForecastResult, export_forecast_handoff_artifacts, forecast_to_signal_frame


def _market_frame(symbol: str = "BTCUSDT") -> pl.DataFrame:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    close = [100.0, 101.0, 100.5, 102.0, 103.0, 102.5]
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


def test_phase5_pipeline_evaluation_smoke(tmp_path: Path) -> None:
    market = _market_frame()
    forecast = AssetForecastResult(
        expected_returns=np.array([[0.1], [-0.1], [0.2], [-0.2], [0.3], [0.1]]),
        timestamps=tuple(market["timestamp"].to_list()),
        asset_ids=("BTCUSDT",),
        metadata={"pipeline": "phase5"},
    )

    handoff_dir = tmp_path / "handoff"
    handoff = export_forecast_handoff_artifacts(
        market_frame=market,
        forecast=forecast,
        output_dir=handoff_dir.as_posix(),
        symbol="BTCUSDT",
        threshold=0.0,
    )
    assert "predictions.parquet" in handoff
    assert "feed_spec.json" in handoff

    signal_frame = forecast_to_signal_frame(market, forecast, symbol="BTCUSDT", threshold=0.0)
    backtest = PolarsSignalBacktester(
        initial_capital=5000.0,
        cost_model=CostModel(fee_rate=0.0005, slippage_rate=0.0005),
    ).run(signal_frame)

    output_dir = tmp_path / "artifacts"
    artifacts = write_backtest_artifacts(
        result_frame=backtest.frame,
        metrics=backtest.metrics,
        run_config={"strategy": "research_model_forecast", "data_path": "fixture.parquet", "initial_capital": 5000.0},
        output_dir=output_dir,
        title="phase5-eval",
        gate_config=GateConfig(report_policy=ReportPolicy.NEVER, min_trades=0),
    )
    validate_ml4t_diagnostic_artifacts(output_dir)
    assert "daily_returns.parquet" in artifacts
    assert (output_dir / "trades.parquet").exists()
