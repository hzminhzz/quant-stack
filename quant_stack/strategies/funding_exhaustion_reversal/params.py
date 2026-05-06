"""Funding exhaustion reversal strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class FundingExhaustionReversalParams(BaseModel):
    funding_zscore_threshold: float = 2.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    require_momentum_turn: bool = True
    require_price_extension: bool = True
    price_extension_threshold: float = 0.02
    require_basis_confirmation: bool = False
    basis_zscore_threshold: float = 1.5
    max_spread_bps: float | None = None
    use_context_filters: bool = True
    exit_on_rsi_midline: bool = True
    exit_rsi_midline: float = 50.0

    @model_validator(mode="after")
    def check_ranges(self) -> "FundingExhaustionReversalParams":
        if not (0.0 < self.rsi_oversold < self.rsi_overbought < 100.0):
            raise ValueError("RSI thresholds must satisfy 0 < rsi_oversold < rsi_overbought < 100")
        if not (0.0 < self.exit_rsi_midline < 100.0):
            raise ValueError("exit_rsi_midline must be between 0 and 100")
        if self.funding_zscore_threshold <= 0:
            raise ValueError("funding_zscore_threshold must be positive")
        if self.price_extension_threshold < 0:
            raise ValueError("price_extension_threshold must be non-negative")
        if self.basis_zscore_threshold <= 0:
            raise ValueError("basis_zscore_threshold must be positive")
        if self.max_spread_bps is not None and self.max_spread_bps < 0:
            raise ValueError("max_spread_bps must be non-negative")
        return self


__all__ = ["FundingExhaustionReversalParams"]
