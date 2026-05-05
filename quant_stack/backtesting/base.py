"""Backtesting engine protocols."""

from __future__ import annotations

from typing import Protocol

import polars as pl

from quant_stack.backtesting.results import BacktestResult


class BacktestEngine(Protocol):
    def run(self, df: pl.DataFrame) -> BacktestResult: ...


__all__ = ["BacktestEngine"]
