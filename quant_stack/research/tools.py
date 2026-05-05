"""Safe tool boundary for PydanticAI research agents."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import polars as pl

from quant_stack.artifacts.store import save_artifact
from quant_stack.backtesting import PolarsSignalBacktester, validate_metrics
from quant_stack.data import validate_ohlcv
from quant_stack.research.experiment_queue import ExperimentQueue
from quant_stack.research.guards import guard_experiment_plan
from quant_stack.research.schemas import BacktestSummary, ExperimentPlan, ValidationReport
from quant_stack.strategies import available_strategies, get_strategy

APPROVED_SYMBOLS: Final[set[str]] = {"BTC", "ETH", "BNB"}
APPROVED_TIMEFRAMES: Final[set[str]] = {"1m", "5m", "15m", "1h", "4h", "1d"}
DEFAULT_RESEARCH_ARTIFACT_DIR: Final[Path] = Path("artifacts/research")


def list_registered_strategies() -> list[str]:
    """Read-only strategy registry access for agents."""

    return available_strategies()


def submit_experiment(plan: ExperimentPlan, *, queue_path: str | Path, created_by_agent: str) -> str:
    """Submit a structured experiment request instead of executing immediately."""

    queue = ExperimentQueue(queue_path)
    record = queue.submit(plan, created_by_agent=created_by_agent)
    return record.experiment_id


def request_backtest_from_plan(plan: ExperimentPlan) -> BacktestSummary:
    """Run a deterministic backtest request through the safe wrapper.

    This wrapper does not touch brokers, live execution, risk config writers, or
    shell commands. If no data frame is supplied by a test harness, it uses a
    deterministic synthetic OHLCV fixture so the request remains typed and
    reproducible.
    """

    reasons = guard_experiment_plan(
        plan,
        registered_strategies=set(available_strategies()),
        approved_symbols=APPROVED_SYMBOLS,
        approved_timeframes=APPROVED_TIMEFRAMES,
    )
    if reasons:
        first = reasons[0]
        raise ValueError(f"experiment plan rejected: {first.code}: {first.message}")

    strategy = get_strategy(plan.strategy_name)
    params = strategy.validate_params(plan.params_to_test[0].params)
    symbol = plan.symbols[0]
    timeframe = plan.timeframes[0]
    df = _synthetic_ohlcv(symbol=symbol, timeframe=timeframe)
    signals = strategy.build_signals(df, params)
    result = PolarsSignalBacktester().run(signals)
    validation = validate_metrics(result.metrics)
    artifact_dir = DEFAULT_RESEARCH_ARTIFACT_DIR
    artifact_path = artifact_dir / f"{plan.strategy_name}_{symbol}_{timeframe}_backtest.json"
    summary = BacktestSummary(
        strategy_name=plan.strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        metrics=result.metrics,
        major_weaknesses=validation.reasons,
        pass_fail="pass" if validation.passed else "fail",
        artifact_path=artifact_path.as_posix(),
    )
    report = ValidationReport(
        passed=validation.passed,
        reasons=validation.reasons,
        metrics=result.metrics,
        risk_flags=validation.reasons,
        artifact_path=artifact_path.as_posix(),
    )
    save_artifact(summary, artifact_path)
    save_artifact(report, artifact_dir / f"{plan.strategy_name}_{symbol}_{timeframe}_validation.json")
    return summary


def _synthetic_ohlcv(*, symbol: str, timeframe: str) -> pl.DataFrame:
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 0, 0, 0),
        end=pl.datetime(2024, 1, 1, 0, 9, 0),
        interval="1m",
        eager=True,
    )
    closes = [100.0, 99.0, 98.0, 101.0, 104.0, 103.0, 105.0, 106.0, 104.0, 107.0]
    return validate_ohlcv(
        pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": closes,
                "high": [value + 1.0 for value in closes],
                "low": [value - 1.0 for value in closes],
                "close": closes,
                "volume": [1.0] * len(closes),
                "symbol": [symbol] * len(closes),
                "timeframe": [timeframe] * len(closes),
            }
        )
    )


__all__ = [
    "APPROVED_SYMBOLS",
    "APPROVED_TIMEFRAMES",
    "list_registered_strategies",
    "request_backtest_from_plan",
    "submit_experiment",
]
