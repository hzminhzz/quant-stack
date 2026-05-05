"""Typed schemas for market intelligence signals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class SignalEvent(BaseModel):
    source: str = Field(..., min_length=1)
    signal_type: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    timestamp: datetime
    value: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    historical_integrity: bool = True

    @model_validator(mode="after")
    def _ensure_timezone(self) -> "SignalEvent":
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        return self


class FundingSignal(BaseModel):
    symbol: str
    timestamp: datetime
    funding_rate: float
    next_funding_time: datetime | None = None


class OpenInterestSignal(BaseModel):
    symbol: str
    timestamp: datetime
    open_interest: float
    open_interest_usd: float | None = None


class BasisSignal(BaseModel):
    symbol: str
    timestamp: datetime
    spot_price: float
    perp_price: float
    basis: float
    basis_bps: float


class OrderbookSignal(BaseModel):
    symbol: str
    timestamp: datetime
    best_bid: float
    best_ask: float
    spread: float
    spread_bps: float
    bid_depth: float
    ask_depth: float
    depth_imbalance: float


class LiquidationSignal(BaseModel):
    symbol: str
    timestamp: datetime
    long_liquidation_notional: float
    short_liquidation_notional: float
    liquidation_imbalance: float


class MarketContextSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    funding_rate: float | None = None
    open_interest: float | None = None
    basis_bps: float | None = None
    spread_bps: float | None = None
    depth_imbalance: float | None = None
    liquidation_imbalance: float | None = None
    unavailable_signals: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "BasisSignal",
    "FundingSignal",
    "LiquidationSignal",
    "MarketContextSnapshot",
    "OpenInterestSignal",
    "OrderbookSignal",
    "SignalEvent",
]
