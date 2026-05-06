"""Schemas for feature-pipeline configuration and validation reporting."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class FeaturePipelineConfig(BaseModel):
    timeframe: str = "1m"
    allow_missing_derivatives: bool = True
    enforce_single_symbol: bool = True
    allow_panel: bool = False
    strict_derivative_causality: bool = True
    add_returns: bool = True
    add_volatility: bool = True
    add_momentum: bool = True
    add_trend: bool = True
    add_bands: bool = True
    add_volume: bool = True
    add_derivatives: bool = True
    add_regimes: bool = True
    add_forced_flow: bool = True


class FeatureWindowConfig(BaseModel):
    return_windows: list[int] = Field(default_factory=lambda: [1, 5, 15, 60])
    vol_windows: list[int] = Field(default_factory=lambda: [20, 60, 240])
    ema_windows: list[int] = Field(default_factory=lambda: [10, 20, 50, 200])
    bb_window: int = 20
    bb_std: float = 2.0
    rsi_window: int = 14
    atr_window: int = 14
    zscore_windows: dict[str, int] = Field(
        default_factory=lambda: {
            "funding": 30,
            "oi": 60,
            "basis": 60,
            "volume_short": 20,
            "volume_long": 60,
            "return": 60,
        }
    )

    @model_validator(mode="after")
    def _validate_positive_windows(self) -> "FeatureWindowConfig":
        checks = [
            *self.return_windows,
            *self.vol_windows,
            *self.ema_windows,
            self.bb_window,
            self.rsi_window,
            self.atr_window,
            *self.zscore_windows.values(),
        ]
        if any(value <= 0 for value in checks):
            raise ValueError("all windows must be positive")
        return self


class FeatureThresholdConfig(BaseModel):
    funding_zscore_extreme: float = 2.0
    oi_zscore_extreme: float = 2.0
    basis_zscore_extreme: float = 2.0
    volume_zscore_spike: float = 2.0
    return_zscore_shock: float = 2.0
    high_vol_quantile: float = 0.75
    low_vol_quantile: float = 0.25
    trend_threshold: float = 0.0


class FeatureValidationReport(BaseModel):
    passed: bool
    errors: list[str]
    warnings: list[str]
    row_count: int
    column_count: int
    missing_required_columns: list[str]
    missing_optional_columns: list[str]
    null_feature_counts: dict[str, int]
    duplicate_timestamp_count: int
    non_monotonic_timestamp: bool
    derivative_causality_violations: int = 0
    panel_detected: bool = False
    unique_symbol_count: int | None = None
    unique_timeframe_count: int | None = None


__all__ = [
    "FeaturePipelineConfig",
    "FeatureThresholdConfig",
    "FeatureValidationReport",
    "FeatureWindowConfig",
]
