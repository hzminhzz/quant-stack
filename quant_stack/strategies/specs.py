"""Strategy contracts for deterministic signal-building modules."""

from __future__ import annotations

from typing import Literal, Protocol

import polars as pl
from pydantic import BaseModel, Field

SignalMode = Literal["vectorized", "path_dependent", "live_stateful"]
BacktestEngineName = Literal["polars", "vectorbt"]


class StrategySpec(BaseModel):
    """Metadata describing a strategy module without execution concerns."""

    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    asset_class: str = "crypto"
    signal_mode: SignalMode
    default_engine: BacktestEngineName


class SignalBuilder(Protocol):
    """Protocol for vectorized strategy signal builders."""

    def build_features(self, df: pl.DataFrame, params: BaseModel) -> pl.DataFrame: ...

    def build_signals(self, df: pl.DataFrame, params: BaseModel) -> pl.DataFrame: ...


class LiveStateAdapter(Protocol):
    """Protocol marker for future stateful live adapters."""

    def step(self, row: object) -> object: ...


__all__ = ["BacktestEngineName", "LiveStateAdapter", "SignalBuilder", "SignalMode", "StrategySpec"]
