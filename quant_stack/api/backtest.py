"""Agent-bridge backtest execution helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from .schemas import BacktestArtifact, BacktestRequest, BacktestSummary, BatchBacktestRequest, BatchBacktestSummary, RunStatus
from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.data import load_ohlcv_parquet
from quant_stack.reporting.backtest_report import GateConfig, ReportPolicy, write_backtest_artifacts
from quant_stack.strategies import get_strategy
from quant_stack.strategies.specs import validate_engine_compatibility


def _filter_by_date(df: pl.DataFrame, start: str | None, end: str | None) -> pl.DataFrame:
    if start is None and end is None:
        return df
    out = df
    if start:
        out = out.filter(pl.col("timestamp") >= datetime.fromisoformat(start))
    if end:
        out = out.filter(pl.col("timestamp") <= datetime.fromisoformat(end))
    return out


def _run_id(prefix: str = "bt") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"


def _to_backtest_summary(
    *,
    run_id: str,
    strategy: str,
    timeframe: str,
    rows: int,
    metrics: dict[str, object],
    artifact_refs: BacktestArtifact,
    symbol: str = "UNKNOWN",
    status: RunStatus = "ok",
    start: str | None = None,
    end: str | None = None,
    warnings: list[str] | None = None,
) -> BacktestSummary:
    normalized_metrics: dict[str, float | int | None] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            normalized_metrics[key] = int(value)
        elif isinstance(value, (int, float)) or value is None:
            normalized_metrics[key] = value
    return BacktestSummary(
        run_id=run_id,
        status=status,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        rows=rows,
        start=start,
        end=end,
        metrics=normalized_metrics,
        warnings=warnings or [],
        artifact_refs=artifact_refs,
    )


def run_backtest(request: BacktestRequest) -> BacktestSummary:
    """Run one deterministic backtest and return agent-safe summary."""

    df = load_ohlcv_parquet(request.data_path, validate=True)
    df = _filter_by_date(df, request.start, request.end)

    strategy = get_strategy(request.strategy)
    validate_engine_compatibility(strategy.spec, "polars")
    params = strategy.validate_params(request.params)
    signals = strategy.build_signals(df, params)

    cost_model = CostModel(
        fee_rate=request.cost_model.fee_rate,
        slippage_rate=request.cost_model.slippage_bps / 10_000.0,
    )
    result = PolarsSignalBacktester(initial_capital=request.initial_capital, cost_model=cost_model).run(signals)

    run_id = _run_id()
    output_dir = Path("artifacts") / "api" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    run_config = {
        "strategy": request.strategy,
        "data_path": request.data_path,
        "params": params.model_dump(),
        "fee_rate": request.cost_model.fee_rate,
        "slippage_bps": request.cost_model.slippage_bps,
        "start": request.start,
        "end": request.end,
        "rows_used": len(df),
        "output_mode": request.output_mode,
    }
    artifacts = write_backtest_artifacts(
        result_frame=result.frame,
        metrics=result.metrics,
        run_config=run_config,
        output_dir=output_dir,
        title=f"{request.strategy} API Backtest",
        gate_config=GateConfig(report_policy=ReportPolicy.NEVER),
    )

    artifact_refs = BacktestArtifact(
        run_id=run_id,
        metrics_path=str(artifacts["summary.json"]),
        summary_path=str(artifacts["receipt.md"]),
        equity_curve_path=str(artifacts.get("report.html")) if artifacts.get("report.html") else None,
        trades_path=str(artifacts.get("trades.parquet")) if artifacts.get("trades.parquet") else None,
        diagnostics_path=str(artifacts.get("gate_result.json")) if artifacts.get("gate_result.json") else None,
        config_path=str(artifacts.get("run_config.json")) if artifacts.get("run_config.json") else None,
    )
    return _to_backtest_summary(
        run_id=run_id,
        strategy=request.strategy,
        symbol=request.symbol or "UNKNOWN",
        timeframe=request.timeframe,
        rows=len(df),
        start=request.start,
        end=request.end,
        metrics=result.metrics,
        artifact_refs=artifact_refs,
        status="ok",
    )


def run_batch_backtest(request: BatchBacktestRequest) -> BatchBacktestSummary:
    """Run parameter batch and return top-N summaries by cumulative return."""

    results: list[BacktestSummary] = []
    failed = 0
    for params in request.param_matrix:
        single = BacktestRequest(
            strategy=request.strategy,
            data_path=request.data_path,
            symbol=request.symbol,
            timeframe=request.timeframe,
            params=params,
            engine=request.engine,
            cost_model=request.cost_model,
            output_mode=request.output_mode,
        )
        try:
            results.append(run_backtest(single))
        except Exception:
            failed += 1

    ranked = sorted(results, key=lambda s: float(s.metrics.get("cumulative_return") or 0.0), reverse=True)
    return BatchBacktestSummary(
        strategy=request.strategy,
        total_candidates=len(request.param_matrix),
        completed_candidates=len(results),
        failed_candidates=failed,
        top_results=ranked[: request.top_n],
    )


__all__ = ["run_backtest", "run_batch_backtest"]
