"""Cost models for deterministic backtests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CostModel(BaseModel):
    """Per-position-change transaction cost model."""

    fee_rate: float = Field(0.0, ge=0.0)
    slippage_rate: float = Field(0.0, ge=0.0)

    @property
    def total_rate(self) -> float:
        return self.fee_rate + self.slippage_rate


__all__ = ["CostModel"]
