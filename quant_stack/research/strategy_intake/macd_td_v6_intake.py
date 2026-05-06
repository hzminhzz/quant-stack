"""MACD-TD V6 Strategy intake pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from quant_stack.research.strategy_intake.macd_td_v6_schemas import (
    MACDTDExperimentPlan,
    MACDTDLeakageAudit,
    MACDTDParams,
    MACDTDStrategyIdea,
    MACDTDSourceStrategySummary,
    MACDTDFeatureAvailability,
    MACDTDExecutionSemanticsAudit,
)


def load_intake_query(yaml_path: str | Path) -> dict[str, Any]:
    """Load and parse intake query YAML."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return data


def create_strategy_idea() -> MACDTDStrategyIdea:
    """Create the MACD-TD V6 strategy idea from the external strategy description."""
    return MACDTDStrategyIdea(
        name="macd_td_v6",
        hypothesis=(
            "MACD divergence on 15m may identify exhaustion/reversal entries, while "
            "multi-timeframe TD9 signals and trailing stops may improve exit timing "
            "and protect profits."
        ),
        entry_logic=(
            "Long: Bullish MACD divergence on 15m with strength >= min_divergence_strength. "
            "Optional buy filter: RSI < buy_rsi_threshold OR close < EMA60 OR volume_ratio > buy_volume_ratio (2 of 3). "
            "Short: Bearish MACD divergence on 15m with strength >= min_divergence_strength."
        ),
        exit_logic=(
            "Partial exits: 1m TD9 opposite closes 25%, 3m TD9 opposite closes 20%, 5m TD9 opposite closes 25%. "
            "Full close: 15m opposite TD9, optional 30m opposite TD9. "
            "Initial stop: divergence low - ATR*1.5 (long), divergence high + ATR*1.5 (short)."
        ),
        risk_logic=(
            "Trailing stop: long trails using max(highest - ATR*trailing_stop_atr, highest*(1-trailing_stop_pct)). "
            "Short trails using min(lowest + ATR*trailing_stop_atr, lowest*(1+trailing_stop_pct)). "
            "Position sizing: risk_per_trade * equity, scaled by strength multiplier, capped at max_position_value_pct."
        ),
        timeframes=["15m", "1m", "3m", "5m", "30m"],
        required_features=[
            "macd_12_26_9",
            "macd_8_17_6",
            "atr_14",
            "ema_20",
            "ema_60",
            "rsi_14",
            "volume_ratio",
            "td_setup",
            "local_extrema",
            "divergence_candidates",
        ],
        known_risks=[
            "Multi-timeframe alignment ambiguity",
            "Local extrema confirmation delay",
            "Partial exit price assumption",
            "Trailing stop intrabar execution",
        ],
        leakage_risks=[
            "Same-bar execution (signal at close, enter at close)",
            "Nearest timestamp matching (future data leakage)",
            "Divergence known before confirmation",
        ],
    )


def create_experiment_plan(
    query: dict[str, Any],
) -> MACDTDExperimentPlan:
    """Create experiment plan from query."""
    strategy = query.get("strategy", {})
    params = query.get("params", {})
    data = query.get("data", {})
    artifacts = query.get("artifacts", {})

    return MACDTDExperimentPlan(
        symbols=query.get("symbols", ["ETH-USDT", "BTC-USDT", "BNB-USDT"]),
        source_timeframe=data.get("source_timeframe", "1m"),
        derived_timeframes=data.get("derived_timeframes", ["3m", "5m", "15m", "30m"]),
        train_period="2022-01-01 to 2023-12-31",
        test_period="2024-01-01 to 2025-12-31",
        fee_bps=params.get("fee_bps", 5.0),
        slippage_bps=params.get("slippage_bps", 2.0),
        execution_lag_policy=params.get("execution_lag_policy", "next_15m_open"),
        data_mode=data.get("mode", "local_or_synthetic"),
        artifacts_dir=artifacts.get("output_dir", "artifacts/research/macd_td_v6_intake_v1"),
    )


def create_source_strategy_summary() -> MACDTDSourceStrategySummary:
    """Create summary of the external strategy source."""
    return MACDTDSourceStrategySummary(
        indicators=[
            "MACD (12,26,9)",
            "Fast MACD (8,17,6)",
            "ATR (14)",
            "EMA (20)",
            "EMA (60)",
            "RSI (14)",
            "Volume ratio (20-period MA)",
            "TD9 setup signals",
        ],
        entry_rules=[
            "Long: Bullish divergence on 15m (price lower low, MACD higher low)",
            "Divergence strength >= min_divergence_strength (default 0.25)",
            "Optional buy filter: 2 of 3 (RSI<40, close<EMA60, volume_ratio>0.8)",
            "Short: Bearish divergence on 15m (price higher high, MACD lower high)",
            "Divergence strength >= min_divergence_strength",
        ],
        exit_rules=[
            "1m TD9 opposite signal closes 25%",
            "3m TD9 opposite signal closes 20%",
            "5m TD9 opposite signal closes 25%",
            "15m TD9 opposite signal closes full",
            "Optional: 30m TD9 opposite signal closes full",
        ],
        add_reentry_rules=[
            "15m TD9 same-direction after entry adds 30% if in profit and outside protection period",
            "3m or 5m same-direction TD9 can add back reduced size after partial exit",
        ],
        trailing_stop_rules=[
            "Long: stop = max(highest - ATR*2.0, highest * 0.95)",
            "Short: stop = min(lowest + ATR*2.0, lowest * 1.05)",
            "Update only on completed bars",
        ],
        position_sizing_rules=[
            "Risk per trade: 5% of equity",
            "Strength multiplier applied to size",
            "Max position: 20% of equity",
        ],
        timeframes=["15m (entry)", "1m/3m/5m/30m (management)"],
        data_dependencies=[
            "15m OHLCV for entry signals",
            "1m, 3m, 5m, 30m OHLCV for exit signals",
            "Binance klines API (original)",
        ],
        non_deterministic_assumptions=[
            "Same-bar execution (enter at close of signal bar)",
            "Nearest timestamp matching for multi-timeframe alignment",
            "Current close used for partial exits during iteration",
        ],
    )


def create_feature_availability() -> MACDTDFeatureAvailability:
    """Create feature availability report for quant_stack."""
    return MACDTDFeatureAvailability(
        macd="available",
        atr="available",
        ema="available",
        rsi="available",
        volume_ratio="available",
        local_extrema="partially_available",
        td_setup="missing",
        divergence_detection="missing",
        multi_timeframe_asof="available",
        path_dependent_partial_exits="should_implement_later",
        trailing_stops="should_implement_later",
    )


def create_execution_semantics_audit() -> MACDTDExecutionSemanticsAudit:
    """Create execution semantics audit for safe implementation."""
    return MACDTDExecutionSemanticsAudit(
        primary_event_clock="15m completed bars",
        lower_timeframe_alignment="asof_backward (select bar with close_time <= current_15m_close_time)",
        extrema_confirmation_policy="delayed_until_confirmed (divergence confirmed at bar t, extrema at t-k)",
        stop_fill_policy="conservative_stop_price (stop fills if touched, worst case)",
        same_bar_event_ordering="conservative_adverse_first (stop before exit, exit before add)",
        entry_execution="next_15m_open (enter at bar t+1 open, not t close)",
        trailing_stop_update_policy="completed_bars_only (update only using bars available at event time)",
        partial_exit_execution="next_lower_tf_bar_open (conservative)",
        full_close_execution="next_15m_bar_open_after_confirmed",
        cost_application="fees and slippage apply to every entry, add, partial exit, full exit, and stop",
    )


def create_leakage_audit() -> MACDTDLeakageAudit:
    """Create leakage audit for MACD-TD V6 strategy."""
    return MACDTDLeakageAudit(
        nearest_timestamp_leakage_risk=True,
        same_bar_execution_risk=True,
        local_extrema_confirmation_delay_risk=True,
        multi_timeframe_alignment_risk=True,
        trailing_stop_intrabar_assumption_risk=True,
        partial_exit_price_assumption_risk=True,
        live_api_dependency_risk=False,
        pandas_talib_dependency_risk=True,
        verdict="eligible_with_risks",
        findings={
            "same_bar_execution": "Original script enters at current close when signal detected - lookahead risk. Fix: enter at next bar open.",
            "nearest_timestamp_matching": "Original uses absolute nearest timestamp which can select future bars. Fix: use asof backward semantics only.",
            "local_extrema_confirmation": "Divergence detection uses window requiring bars after extrema. Fix: use confirmation timestamp, not extrema timestamp.",
            "multi_timeframe_alignment": "Lower timeframe selection must use backward asof only. Fix: ensure close_time <= current bar close_time.",
            "trailing_stop_intrabar": "Check against 15m high/low but use 5m close for management. Fix: document stop execution assumption conservatively.",
            "partial_exit_price": "Uses current 5m close during 15m iteration. Fix: align with completed 5m bars only.",
            "pandas_talib": "Original uses pandas/TA-Lib. Core must use Polars/NumPy. Fix: reimplement indicators using quant_stack indicators.",
        },
    )


def generate_artifacts(
    query_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Generate all artifacts for Phase 19A."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    query = load_intake_query(query_path)
    query_normalized = {
        "query_id": "macd_td_v6_intake_v1",
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
    }

    strategy_idea = create_strategy_idea()
    experiment_plan = create_experiment_plan(query)
    source_summary = create_source_strategy_summary()
    feature_report = create_feature_availability()
    exec_semantics = create_execution_semantics_audit()
    leakage_audit = create_leakage_audit()

    artifacts = {
        "query_normalized": output_path / "query.normalized.json",
        "strategy_idea": output_path / "strategy_idea.json",
        "experiment_plan": output_path / "experiment_plan.json",
        "source_strategy_summary": output_path / "source_strategy_summary.json",
        "feature_availability_report": output_path / "feature_availability_report.json",
        "execution_semantics_audit": output_path / "execution_semantics_audit.json",
        "leakage_audit": output_path / "leakage_audit.json",
    }

    with open(artifacts["query_normalized"], "w") as f:
        json.dump(query_normalized, f, indent=2)

    with open(artifacts["strategy_idea"], "w") as f:
        json.dump(strategy_idea.model_dump(), f, indent=2)

    with open(artifacts["experiment_plan"], "w") as f:
        json.dump(experiment_plan.model_dump(), f, indent=2)

    with open(artifacts["source_strategy_summary"], "w") as f:
        json.dump(source_summary.model_dump(), f, indent=2)

    with open(artifacts["feature_availability_report"], "w") as f:
        json.dump(feature_report.model_dump(), f, indent=2)

    with open(artifacts["execution_semantics_audit"], "w") as f:
        json.dump(exec_semantics.model_dump(), f, indent=2)

    with open(artifacts["leakage_audit"], "w") as f:
        json.dump(leakage_audit.model_dump(), f, indent=2)

    return artifacts


__all__ = [
    "load_intake_query",
    "create_strategy_idea",
    "create_experiment_plan",
    "create_source_strategy_summary",
    "create_feature_availability",
    "create_execution_semantics_audit",
    "create_leakage_audit",
    "generate_artifacts",
]