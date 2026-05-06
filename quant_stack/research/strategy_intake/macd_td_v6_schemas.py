"""Typed schemas for MACD-TD V6 strategy intake."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MACDTDParams(BaseModel):
    """Parameters for MACD-TD V6 strategy."""

    macd_fast_period: int = Field(12, ge=1)
    macd_slow_period: int = Field(26, ge=1)
    macd_signal_period: int = Field(9, ge=1)
    macd_alt_fast_period: int = Field(8, ge=1)
    macd_alt_slow_period: int = Field(17, ge=1)
    macd_alt_signal_period: int = Field(6, ge=1)
    atr_period: int = Field(14, ge=1)
    ema_fast_period: int = Field(20, ge=1)
    ema_slow_period: int = Field(60, ge=1)
    rsi_period: int = Field(14, ge=1)
    volume_ma_period: int = Field(20, ge=1)
    min_divergence_strength: float = Field(0.25, ge=0.0, le=1.0)
    enable_buy_filter: bool = True
    buy_rsi_threshold: float = Field(40.0, ge=0.0, le=100.0)
    buy_volume_ratio: float = Field(0.8, ge=0.0)
    enable_30min_clear: bool = True
    min_bars_before_action: int = Field(1, ge=0)
    initial_add_size: float = Field(0.3, ge=0.0, le=1.0)
    trailing_stop_atr: float = Field(2.0, ge=0.0)
    trailing_stop_pct: float = Field(0.05, ge=0.0, le=1.0)
    risk_per_trade: float = Field(0.05, ge=0.0, le=1.0)
    max_position_value_pct: float = Field(0.20, ge=0.0, le=1.0)
    tp_1m_ratio: float = Field(0.25, ge=0.0, le=1.0)
    tp_3m_ratio: float = Field(0.20, ge=0.0, le=1.0)
    tp_5m_ratio: float = Field(0.25, ge=0.0, le=1.0)


class MACDTDStrategyIdea(BaseModel):
    """Strategy idea for MACD-TD V6 strategy."""

    name: str = "macd_td_v6"
    hypothesis: str = Field(..., min_length=10)
    entry_logic: str = Field(..., min_length=5)
    exit_logic: str = Field(..., min_length=5)
    risk_logic: str = Field(..., min_length=5)
    timeframes: list[str]
    required_features: list[str]
    known_risks: list[str] = Field(default_factory=list)
    leakage_risks: list[str] = Field(default_factory=list)


class MACDTDExperimentPlan(BaseModel):
    """Experiment plan for MACD-TD V6 strategy backtest."""

    symbols: list[str] = Field(..., min_length=1)
    source_timeframe: str = "1m"
    derived_timeframes: list[str] = Field(default_factory=lambda: ["3m", "5m", "15m", "30m"])
    train_period: str = Field(..., min_length=1)
    test_period: str = Field(..., min_length=1)
    fee_bps: float = Field(5.0, ge=0.0)
    slippage_bps: float = Field(2.0, ge=0.0)
    execution_lag_policy: str = "next_15m_open"
    data_mode: str = "local_or_synthetic"
    artifacts_dir: str = "artifacts/research/macd_td_v6_intake_v1"


class MACDTDLeakageAudit(BaseModel):
    """Leakage audit results for MACD-TD V6 strategy."""

    nearest_timestamp_leakage_risk: bool = False
    same_bar_execution_risk: bool = False
    local_extrema_confirmation_delay_risk: bool = False
    multi_timeframe_alignment_risk: bool = False
    trailing_stop_intrabar_assumption_risk: bool = False
    partial_exit_price_assumption_risk: bool = False
    live_api_dependency_risk: bool = False
    pandas_talib_dependency_risk: bool = False
    verdict: Literal["eligible", "eligible_with_risks", "not_eligible"] = "eligible"
    findings: dict[str, str] = Field(default_factory=dict)


class MACDTDSourceStrategySummary(BaseModel):
    """Summary of source strategy from external script."""

    indicators: list[str]
    entry_rules: list[str]
    exit_rules: list[str]
    add_reentry_rules: list[str]
    trailing_stop_rules: list[str]
    position_sizing_rules: list[str]
    timeframes: list[str]
    data_dependencies: list[str]
    non_deterministic_assumptions: list[str] = Field(default_factory=list)


class MACDTDExecutionSemanticsAudit(BaseModel):
    """Audit of execution semantics for safe implementation."""

    primary_event_clock: str
    lower_timeframe_alignment: str
    extrema_confirmation_policy: str
    stop_fill_policy: str
    same_bar_event_ordering: str
    entry_execution: str
    trailing_stop_update_policy: str
    partial_exit_execution: str
    full_close_execution: str
    cost_application: str


class MACDTDFeatureAvailability(BaseModel):
    """Report on feature availability in quant_stack."""

    macd: str = "available"
    atr: str = "available"
    ema: str = "available"
    rsi: str = "available"
    volume_ratio: str = "available"
    local_extrema: str = "partially_available"
    td_setup: str = "missing"
    divergence_detection: str = "missing"
    multi_timeframe_asof: str = "available"
    path_dependent_partial_exits: str = "should_implement_later"
    trailing_stops: str = "should_implement_later"


__all__ = [
    "MACDTDParams",
    "MACDTDStrategyIdea",
    "MACDTDExperimentPlan",
    "MACDTDLeakageAudit",
    "MACDTDSourceStrategySummary",
    "MACDTDExecutionSemanticsAudit",
    "MACDTDFeatureAvailability",
]