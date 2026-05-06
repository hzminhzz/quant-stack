"""OI-confirmed trend continuation strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class OIConfirmedTrendParams(BaseModel):
    trend_strength_threshold: float = 0.0
    min_ema_dist_20: float = 0.0
    require_oi_expansion: bool = True
    oi_zscore_threshold: float = 1.0
    oi_change_pct_threshold: float = 0.0
    avoid_funding_extreme: bool = True
    funding_crowded_threshold: float = 1.5
    avoid_basis_extreme: bool = True
    basis_crowded_threshold: float = 1.5
    max_spread_bps: float | None = None
    use_context_filters: bool = True
    exit_on_trend_reversal: bool = True

    @model_validator(mode="after")
    def check_thresholds(self) -> "OIConfirmedTrendParams":
        if self.max_spread_bps is not None and self.max_spread_bps < 0:
            raise ValueError("max_spread_bps must be non-negative")
        return self


__all__ = ["OIConfirmedTrendParams"]
