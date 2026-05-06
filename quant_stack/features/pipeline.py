"""Composable feature pipeline for canonical Bybit market datasets."""

from __future__ import annotations

import polars as pl

from quant_stack.features.bands import add_bollinger_features
from quant_stack.features.derivatives import add_derivatives_features
from quant_stack.features.forced_flow import add_forced_flow_proxy_features
from quant_stack.features.momentum import add_momentum_features
from quant_stack.features.regimes import add_regime_features
from quant_stack.features.returns import add_return_features
from quant_stack.features.schemas import FeaturePipelineConfig, FeatureThresholdConfig, FeatureWindowConfig
from quant_stack.features.trend import add_trend_features
from quant_stack.features.validation import (
    assert_no_future_columns,
    check_derivative_causality,
    check_single_symbol_timeframe,
    validate_feature_input,
    validate_feature_output,
)
from quant_stack.features.volatility import add_volatility_features
from quant_stack.features.volume import add_volume_features


def get_required_base_columns() -> list[str]:
    return ["timestamp", "available_at", "open", "high", "low", "close", "volume"]


def get_optional_derivative_columns() -> list[str]:
    return ["funding_rate", "open_interest", "basis", "oi_change_pct", "turnover", "spot_close"]


def get_feature_columns(df: pl.DataFrame) -> list[str]:
    base = set(get_required_base_columns() + ["symbol", "timeframe"])
    return [col for col in df.columns if col not in base]


def build_feature_dataset(
    df: pl.DataFrame,
    config: FeaturePipelineConfig | None = None,
    windows: FeatureWindowConfig | None = None,
    thresholds: FeatureThresholdConfig | None = None,
) -> pl.DataFrame:
    cfg = config or FeaturePipelineConfig()
    win = windows or FeatureWindowConfig()
    thr = thresholds or FeatureThresholdConfig()

    input_report = validate_feature_input(df, require_derivatives=not cfg.allow_missing_derivatives)
    panel_detected, unique_symbol_count, unique_timeframe_count = check_single_symbol_timeframe(df)
    if cfg.enforce_single_symbol and panel_detected and not cfg.allow_panel:
        raise ValueError(
            "feature input validation failed: multi-symbol/timeframe panel detected; grouped rolling is not implemented in this phase"
        )

    causality_violations, causality_errors, causality_warnings = check_derivative_causality(
        df,
        strict=cfg.strict_derivative_causality,
    )
    input_report.derivative_causality_violations = causality_violations
    input_report.panel_detected = panel_detected
    input_report.unique_symbol_count = unique_symbol_count
    input_report.unique_timeframe_count = unique_timeframe_count
    input_report.errors.extend(causality_errors)
    input_report.warnings.extend(causality_warnings)
    input_report.passed = len(input_report.errors) == 0

    if not input_report.passed:
        raise ValueError("feature input validation failed: " + "; ".join(input_report.errors))

    out = df
    if cfg.add_returns:
        out = add_return_features(out, win.return_windows)
    if cfg.add_volatility:
        out = add_volatility_features(out, win.vol_windows, win.atr_window)
    if cfg.add_momentum:
        out = add_momentum_features(out, win.rsi_window)
    if cfg.add_trend:
        out = add_trend_features(out, win.ema_windows)
    if cfg.add_bands:
        out = add_bollinger_features(out, win.bb_window, win.bb_std)
    if cfg.add_volume:
        out = add_volume_features(out)
    if cfg.add_derivatives:
        out = add_derivatives_features(out, win, thr, allow_missing=cfg.allow_missing_derivatives)
    if cfg.add_regimes:
        out = add_regime_features(out, win, thr, allow_missing=cfg.allow_missing_derivatives)
    if cfg.add_forced_flow:
        out = add_forced_flow_proxy_features(out, thr)

    assert_no_future_columns(out)
    output_report = validate_feature_output(out)
    if not output_report.passed:
        raise ValueError("feature output validation failed: " + "; ".join(output_report.errors))
    return out


__all__ = [
    "build_feature_dataset",
    "get_feature_columns",
    "get_optional_derivative_columns",
    "get_required_base_columns",
]
