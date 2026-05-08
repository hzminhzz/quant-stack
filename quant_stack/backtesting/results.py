"""Backtest result models."""

from __future__ import annotations

from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict, Field

class BacktestResult(BaseModel):
    """Normalized output from a backtesting engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame: pl.DataFrame
    metrics: dict[str, Any] = Field(default_factory=dict)
    trades: list[float] = Field(default_factory=list)


__all__ = ["BacktestResult"]
