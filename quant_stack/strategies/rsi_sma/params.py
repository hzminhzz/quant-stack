"""RSI/SMA strategy parameters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RSISMAParams(BaseModel):
    short_sma: int = Field(20)
    long_sma: int = Field(100)
    rsi_period: int = Field(14)
    rsi_threshold: float = Field(35.0)
    rsi_side: Literal["below", "above"] = Field("below")

    @field_validator("short_sma", "long_sma", "rsi_period")
    @classmethod
    def check_positive_windows(cls, value: int) -> int:
        if value <= 1:
            raise ValueError("strategy periods must be greater than 1")
        return value

    @field_validator("rsi_threshold")
    @classmethod
    def check_rsi_threshold(cls, value: float) -> float:
        if value <= 5 or value >= 95:
            raise ValueError("RSI threshold must be between 5 and 95")
        return value

    @model_validator(mode="after")
    def check_window_order(self) -> "RSISMAParams":
        if self.short_sma >= self.long_sma:
            raise ValueError("short_sma must be less than long_sma")
        return self


__all__ = ["RSISMAParams"]
