"""Grid strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GridParams(BaseModel):
    num_levels: int = Field(20, ge=2)
    grid_width_pct: float = Field(0.10, gt=0)
    fee_pct: float = Field(0.0002, ge=0)


__all__ = ["GridParams"]
