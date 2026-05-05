"""Bollinger breakout strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class BBBreakoutParams(BaseModel):
    bb_length: int = Field(20)
    bb_std: float = Field(1.0)
    regime_sma: int = Field(200)

    @field_validator("bb_length", "regime_sma")
    @classmethod
    def check_positive_windows(cls, value: int) -> int:
        if value <= 1:
            raise ValueError("strategy periods must be greater than 1")
        return value

    @field_validator("bb_std")
    @classmethod
    def check_std(cls, value: float) -> float:
        if value < 0.1 or value > 5.0:
            raise ValueError("bb_std must be between 0.1 and 5.0")
        return value


__all__ = ["BBBreakoutParams"]
