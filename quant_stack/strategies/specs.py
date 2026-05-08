"""Strategy contracts for deterministic signal-building modules."""

from __future__ import annotations

from typing import Literal, Protocol

import polars as pl
from pydantic import BaseModel, Field

SignalMode = Literal["vectorized", "path_dependent", "live_stateful"]
BacktestEngineName = Literal["polars", "vectorbt", "stateful", "grid_dca", "event_driven"]


class EngineCompatibilityError(ValueError):
    """Raised when a strategy is incompatible with a requested engine."""


class StrategyCapabilities(BaseModel):
    """Engine selection criteria for a strategy."""

    path_dependent: bool = False
    multi_leg: bool = False
    average_price_dependent: bool = False
    supports_vectorized: bool = True
    requires_bid_ask: bool = False
    requires_event_log: bool = False
    requires_margin_model: bool = False


class StrategySpec(BaseModel):
    """Metadata describing a strategy module without execution concerns."""

    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    asset_class: str = "crypto"
    signal_mode: SignalMode
    default_engine: BacktestEngineName
    capabilities: StrategyCapabilities = Field(default_factory=StrategyCapabilities)


class SignalBuilder(Protocol):
    """Protocol for vectorized strategy signal builders."""

    def build_features(self, df: pl.DataFrame, params: BaseModel) -> pl.DataFrame: ...

    def build_signals(self, df: pl.DataFrame, params: BaseModel) -> pl.DataFrame: ...


class LiveStateAdapter(Protocol):
    """Protocol marker for future stateful live adapters."""

    def step(self, row: object) -> object: ...


__all__ = [
    "BacktestEngineName",
    "EngineCompatibilityError",
    "LiveStateAdapter",
    "SignalBuilder",
    "SignalMode",
    "StrategyCapabilities",
    "StrategySpec",
    "validate_engine_compatibility",
    "select_engine",
]


def validate_engine_compatibility(spec: StrategySpec, engine: BacktestEngineName) -> None:
    """Reject invalid strategy/engine combinations before execution."""

    cap = spec.capabilities
    if engine == "polars" and (cap.path_dependent or cap.multi_leg or cap.average_price_dependent):
        raise EngineCompatibilityError(
            f"strategy '{spec.name}' is path-dependent/multi-leg; polars engine is incompatible"
        )
    if engine == "vectorbt" and (cap.multi_leg or cap.average_price_dependent):
        raise EngineCompatibilityError(
            f"strategy '{spec.name}' is multi-leg/average-price-dependent; vectorbt engine is incompatible"
        )
    if engine == "stateful" and not (cap.path_dependent or cap.requires_event_log):
        raise EngineCompatibilityError(
            f"strategy '{spec.name}' does not require stateful execution; choose polars/vectorbt"
        )
    if engine == "grid_dca" and not (cap.multi_leg or cap.average_price_dependent):
        raise EngineCompatibilityError(
            f"strategy '{spec.name}' does not declare grid/DCA capabilities"
        )


def select_engine(spec: StrategySpec) -> BacktestEngineName:
    """Select the appropriate backtest engine based on strategy capabilities."""
    cap = spec.capabilities
    
    if spec.default_engine not in ("polars", "vectorbt"):
        return spec.default_engine
    
    if cap.multi_leg or cap.average_price_dependent:
        return "grid_dca"
    
    if cap.path_dependent or cap.requires_event_log:
        return "stateful"
    
    if cap.supports_vectorized:
        return "vectorbt"
    
    return "polars"
