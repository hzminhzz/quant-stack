"""Agent-callable tool bridge for quant_stack."""

from __future__ import annotations

from typing import Any

from quant_stack.api.artifacts import fetch_summary
from quant_stack.api.backtest import run_backtest, run_batch_backtest
from quant_stack.api.schemas import BacktestRequest, BatchBacktestRequest
from quant_stack.strategies import available_strategies, get_strategy


def strategy_list() -> list[str]:
    """Return available strategy names."""

    return available_strategies()


def strategy_describe(strategy_name: str) -> dict[str, Any]:
    """Return compact strategy metadata and parameter schema."""

    module = get_strategy(strategy_name)
    return {
        "name": module.spec.name,
        "version": module.spec.version,
        "timeframe": module.spec.timeframe,
        "signal_mode": module.spec.signal_mode,
        "default_engine": module.spec.default_engine,
        "capabilities": module.spec.capabilities.model_dump(),
        "params_schema": module.params_model.model_json_schema(),
    }


def backtest_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Typed wrapper for single backtest endpoint."""

    request = BacktestRequest.model_validate(payload)
    return run_backtest(request).model_dump()


def backtest_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """Typed wrapper for batch backtest endpoint."""

    request = BatchBacktestRequest.model_validate(payload)
    return run_batch_backtest(request).model_dump()


def artifact_fetch_summary(summary_path: str) -> dict[str, Any]:
    """Fetch persisted summary artifact by path."""

    return fetch_summary(summary_path)


TOOLS: dict[str, Any] = {
    "strategy.list": strategy_list,
    "strategy.describe": strategy_describe,
    "backtest.run": backtest_run,
    "backtest.batch": backtest_batch,
    "artifact.fetch_summary": artifact_fetch_summary,
}


__all__ = [
    "TOOLS",
    "artifact_fetch_summary",
    "backtest_batch",
    "backtest_run",
    "strategy_describe",
    "strategy_list",
]
