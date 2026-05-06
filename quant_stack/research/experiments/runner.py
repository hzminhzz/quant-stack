"""Phase 18F experiment runner."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import polars as pl

from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.research.experiments.comparison import compare_results
from quant_stack.research.experiments.config import build_mode_params
from quant_stack.research.experiments.report import render_comparison_markdown
from quant_stack.research.experiments.schemas import (
    ExperimentConfig,
    StrategyComparisonReport,
    StrategyExperimentResult,
)
from quant_stack.strategies import get_strategy

Segment = tuple[str, str, int | None, pl.DataFrame]


def run_strategy_experiment(config: ExperimentConfig) -> StrategyComparisonReport:
    dataset_path = Path(config.dataset_path)
    if not dataset_path.exists():
        raise ValueError(f"dataset path does not exist: {dataset_path.as_posix()}")

    strategy = _get_strategy(config.strategy_name)
    _validate_strategy_eligibility(strategy)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = _load_dataset(config)
    segments = _build_segments(frame, config)

    default_params = strategy.validate_params({}).model_dump()
    baseline_params = build_mode_params(default_params, config.baseline_params, context_mode=False)
    context_params = build_mode_params(default_params, config.context_params, context_mode=True)

    baseline_segment_results = _run_segments(
        strategy_name=config.strategy_name,
        mode="baseline",
        segments=segments,
        strategy=strategy,
        params=baseline_params,
        initial_cash=config.initial_cash,
        fee_bps=config.fee_bps,
        slippage_bps=config.slippage_bps,
        output_dir=output_dir,
    )
    context_segment_results = _run_segments(
        strategy_name=config.strategy_name,
        mode="context",
        segments=segments,
        strategy=strategy,
        params=context_params,
        initial_cash=config.initial_cash,
        fee_bps=config.fee_bps,
        slippage_bps=config.slippage_bps,
        output_dir=output_dir,
    )

    baseline_result = _aggregate_mode_result(config.strategy_name, "baseline", baseline_params, baseline_segment_results)
    context_result = _aggregate_mode_result(config.strategy_name, "context", context_params, context_segment_results)

    report = compare_results(
        strategy_name=config.strategy_name,
        baseline_result=baseline_result,
        context_result=context_result,
    )
    report_path = output_dir / "comparison_report.md"
    report_path.write_text(render_comparison_markdown(report), encoding="utf-8")
    _write_json(output_dir / "comparison_report.json", report.model_dump(mode="json"))
    _write_json(
        output_dir / "segments_manifest.json",
        {
            "segments": [
                {
                    "name": name,
                    "role": role,
                    "fold": fold,
                    "row_count": int(seg_frame.height),
                    "start_timestamp": str(seg_frame.select(pl.col("timestamp").min()).item()),
                    "end_timestamp": str(seg_frame.select(pl.col("timestamp").max()).item()),
                    "boundary_rule": "[start, end) for internal splits; explicit test_end inclusive",
                }
                for name, role, fold, seg_frame in segments
            ]
        },
    )
    return report


def _get_strategy(strategy_name: str):
    try:
        return get_strategy(strategy_name)
    except KeyError as exc:
        raise ValueError(f"strategy not registered: {strategy_name}") from exc


def _load_dataset(config: ExperimentConfig) -> pl.DataFrame:
    frame = pl.read_parquet(config.dataset_path)
    required = {"timestamp", "close", "symbol", "timeframe"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"dataset missing required column(s): {', '.join(missing)}")
    frame = frame.sort("timestamp")

    filtered = frame
    filtered = filtered.filter(pl.col("symbol") == config.symbol)
    if filtered.is_empty():
        raise ValueError(f"dataset has no rows for symbol: {config.symbol}")

    filtered = filtered.filter(pl.col("timeframe") == config.timeframe)
    if filtered.is_empty():
        raise ValueError(f"dataset has no rows for timeframe: {config.timeframe}")

    filtered = filtered.filter(
        (pl.col("timestamp") >= pl.lit(config.start)) & (pl.col("timestamp") <= pl.lit(config.end))
    )
    if filtered.is_empty():
        raise ValueError("dataset has no rows in requested [start, end] window")
    return filtered


def _run_mode(
    *,
    strategy_name: str,
    mode: str,
    frame: pl.DataFrame,
    strategy: Any,
    params: dict[str, Any],
    initial_cash: float,
    fee_bps: float,
    slippage_bps: float,
    output_dir: Path,
) -> StrategyExperimentResult:
    validated_params = strategy.validate_params(params)
    try:
        signal_frame = strategy.build_signals(frame, validated_params)
    except ValueError as exc:
        raise ValueError(f"{strategy_name} {mode} signal build failed: {exc}") from exc

    backtester = PolarsSignalBacktester(
        initial_capital=initial_cash,
        cost_model=CostModel(fee_rate=fee_bps / 10_000.0, slippage_rate=slippage_bps / 10_000.0),
    )
    backtest_result = backtester.run(signal_frame)
    metrics = _enrich_metrics(backtest_result.metrics, backtest_result.trades)

    signal_path = output_dir / f"{mode}_signals.parquet"
    equity_path = output_dir / f"{mode}_equity.parquet"
    metrics_path = output_dir / f"{mode}_metrics.json"

    signal_frame.write_parquet(signal_path)
    backtest_result.frame.write_parquet(equity_path)
    _write_json(metrics_path, metrics)

    return StrategyExperimentResult(
        strategy_name=strategy_name,
        mode="baseline" if mode == "baseline" else "context",
        params=validated_params.model_dump(),
        backtest_result={
            "rows": int(backtest_result.frame.height),
            "trade_count": int(len(backtest_result.trades)),
            "generated_at": None,
        },
        metrics=_sanitize_metrics(metrics),
        artifact_paths={
            "signals": signal_path.as_posix(),
            "equity": equity_path.as_posix(),
            "metrics": metrics_path.as_posix(),
        },
    )


def _run_segments(
    *,
    strategy_name: str,
    mode: str,
    segments: list[Segment],
    strategy: Any,
    params: dict[str, Any],
    initial_cash: float,
    fee_bps: float,
    slippage_bps: float,
    output_dir: Path,
) -> list[tuple[str, str, int | None, StrategyExperimentResult]]:
    results: list[tuple[str, str, int | None, StrategyExperimentResult]] = []
    for segment_name, segment_role, fold, segment_frame in segments:
        segment_dir = output_dir / segment_name
        segment_dir.mkdir(parents=True, exist_ok=True)
        mode_result = _run_mode(
            strategy_name=strategy_name,
            mode=mode,
            frame=segment_frame,
            strategy=strategy,
            params=params,
            initial_cash=initial_cash,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            output_dir=segment_dir,
        )
        mode_result.backtest_result["segment_name"] = segment_name
        mode_result.backtest_result["segment_role"] = segment_role
        mode_result.backtest_result["fold"] = fold
        results.append((segment_name, segment_role, fold, mode_result))
    return results


def _aggregate_mode_result(
    strategy_name: str,
    mode: str,
    params: dict[str, Any],
    segment_results: list[tuple[str, str, int | None, StrategyExperimentResult]],
) -> StrategyExperimentResult:
    oos_results = [result for _, role, _, result in segment_results if role == "test"]
    aggregate_metrics = _aggregate_metrics([result.metrics for result in oos_results])
    trade_count = int(sum(float(result.metrics.get("trade_count", 0.0) or 0.0) for result in oos_results))
    return StrategyExperimentResult(
        strategy_name=strategy_name,
        mode="baseline" if mode == "baseline" else "context",
        params=params,
        backtest_result={
            "rows": int(sum(int(result.backtest_result.get("rows", 0)) for result in oos_results)),
            "trade_count": trade_count,
            "generated_at": None,
            "segments": [
                {
                    "name": segment_name,
                    "role": segment_role,
                    "fold": fold,
                    "metrics": result.metrics,
                    "rows": result.backtest_result.get("rows", 0),
                }
                for segment_name, segment_role, fold, result in segment_results
            ],
        },
        metrics=aggregate_metrics,
        artifact_paths={
            "segments_root": "",
        },
    )


def _aggregate_metrics(metrics_list: list[dict[str, Any]]) -> dict[str, Any]:
    if not metrics_list:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "trade_count": 0.0,
            "exposure": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "raw_metrics": {},
        }

    compounded = 1.0
    sharpe_values: list[float] = []
    max_drawdown = 0.0
    trade_count = 0.0
    exposure_values: list[float] = []
    total_wins = 0.0
    total_trades = 0.0
    profit_factors: list[float] = []
    for metrics in metrics_list:
        total_return = float(metrics.get("total_return", 0.0) or 0.0)
        compounded *= 1.0 + total_return
        sharpe_values.append(float(metrics.get("sharpe", 0.0) or 0.0))
        max_drawdown = min(max_drawdown, float(metrics.get("max_drawdown", 0.0) or 0.0))
        segment_trades = float(metrics.get("trade_count", 0.0) or 0.0)
        trade_count += segment_trades
        exposure_values.append(float(metrics.get("exposure", 0.0) or 0.0))
        win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
        total_wins += win_rate * segment_trades
        total_trades += segment_trades
        pf = metrics.get("profit_factor")
        if isinstance(pf, float) and pf is not None and not math.isnan(pf) and not math.isinf(pf):
            profit_factors.append(pf)

    aggregate = {
        "total_return": compounded - 1.0,
        "sharpe": sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0.0,
        "max_drawdown": max_drawdown,
        "trade_count": trade_count,
        "exposure": sum(exposure_values) / len(exposure_values) if exposure_values else 0.0,
        "win_rate": (total_wins / total_trades) if total_trades > 0 else 0.0,
        "profit_factor": (sum(profit_factors) / len(profit_factors)) if profit_factors else 0.0,
        "raw_metrics": {"segments": metrics_list},
    }
    return _sanitize_metrics(aggregate)


def _enrich_metrics(metrics: dict[str, Any], trades: list[float]) -> dict[str, Any]:
    wins = [trade for trade in trades if trade > 0]
    losses = [trade for trade in trades if trade < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "total_return": float(metrics.get("cumulative_return", 0.0) or 0.0),
        "sharpe": float(metrics.get("smart_sharpe", 0.0) or 0.0),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0) or 0.0),
        "trade_count": float(len(trades)),
        "exposure": float(metrics.get("time_in_market", 0.0) or 0.0),
        "win_rate": float(len(wins) / len(trades)) if trades else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0),
        "raw_metrics": metrics,
    }


def _sanitize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            sanitized[key] = None
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_metrics(value)
        else:
            sanitized[key] = value
    return sanitized


def _validate_strategy_eligibility(strategy: Any) -> None:
    if strategy.spec.signal_mode != "vectorized":
        raise ValueError(f"strategy not eligible for Phase 18F harness: signal_mode={strategy.spec.signal_mode}")
    if strategy.spec.default_engine != "polars":
        raise ValueError(f"strategy not eligible for Phase 18F harness: default_engine={strategy.spec.default_engine}")


def _build_segments(frame: pl.DataFrame, config: ExperimentConfig) -> list[Segment]:
    if config.walk_forward_enabled:
        return _build_walk_forward_segments(frame, config)

    if config.train_start is not None and config.train_end is not None and config.test_start is not None and config.test_end is not None:
        train_frame = frame.filter((pl.col("timestamp") >= pl.lit(config.train_start)) & (pl.col("timestamp") < pl.lit(config.train_end)))
        test_frame = frame.filter((pl.col("timestamp") >= pl.lit(config.test_start)) & (pl.col("timestamp") <= pl.lit(config.test_end)))
        if train_frame.is_empty() or test_frame.is_empty():
            raise ValueError("train/test split produced empty segment(s)")
        return [("train", "train", None, train_frame), ("test", "test", None, test_frame)]

    return [("full", "test", None, frame)]


def _build_walk_forward_segments(frame: pl.DataFrame, config: ExperimentConfig) -> list[Segment]:
    train_bars = int(config.walk_forward_train_bars or 0)
    test_bars = int(config.walk_forward_test_bars or 0)
    step_bars = int(config.walk_forward_step_bars or test_bars)
    total = frame.height
    segments: list[Segment] = []

    start_idx = 0
    fold = 0
    while True:
        train_end = start_idx + train_bars
        test_end = train_end + test_bars
        if test_end > total:
            break
        train_seg = frame.slice(start_idx, train_bars)
        test_seg = frame.slice(train_end, test_bars)
        segments.append((f"wf_fold_{fold:02d}_train", "train", fold, train_seg))
        segments.append((f"wf_fold_{fold:02d}_test", "test", fold, test_seg))
        fold += 1
        start_idx += step_bars

    if not segments:
        raise ValueError("walk-forward segmentation produced no folds with current bar settings")
    return segments


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


__all__ = ["run_strategy_experiment"]
