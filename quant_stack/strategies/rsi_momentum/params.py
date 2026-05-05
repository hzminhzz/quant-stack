"""RSI Momentum strategy parameters."""

from __future__ import annotations
from pydantic import BaseModel, Field

class RSIMomentumParams(BaseModel):
    rsi_period: int = Field(14)
    rsi_upper: float = Field(70.0)
    rsi_lower: float = Field(30.0)
    rsi_exit: float = Field(50.0)
    symbol: str = Field("BTC-USDT")
    timeframe: str = Field("4h")
    fee_bps: float = Field(5.0)
    slippage_bps: float = Field(2.0)
    execution_lag_bars: int = Field(1)
