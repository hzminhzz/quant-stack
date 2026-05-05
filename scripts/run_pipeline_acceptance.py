"""Run the deterministic Phase 17 pipeline acceptance harness."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant_stack.backtesting.contracts import ValidationResult, validate_metrics
from quant_stack.backtesting.polars_engine import PolarsSignalBacktester
from quant_stack.data import validate_ohlcv
from quant_stack.intelligence.regime_context import apply_context_gate_to_signals
from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.snapshot import build_context_frame
from quant_stack.intelligence.store import save_events
from quant_stack.research.experiment_queue import OptimizationRequestRecord
from quant_stack.research.acceptance_artifacts import AcceptanceArtifactSet, Phase17ReportHelper
from quant_stack.research.fixtures import (
    DEFAULT_PHASE17_SYMBOL,
    load_phase17_btc_ohlcv_fixture,
    load_phase17_intelligence_events,
    save_phase17_btc_ohlcv_fixture,
    save_phase17_intelligence_events,
)
from quant_stack.research.optimization.acceptance_query import AcceptanceQuery, load_acceptance_query
from quant_stack.research.optimization.schemas import AcceptanceCriteria, OptimizationRequest
from quant_stack.strategies.registry import get_strategy


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase 17 pipeline acceptance harness")
    parser.add_argument("--query", required=True, help="Path to an acceptance query YAML file")
    parser.add_argument("--output-dir", required=True, help="Directory for JSON and markdown artifacts")
    parser.add_argument("--fixture-root", default=None, help="Optional root for persisted deterministic OHLCV fixtures")
    parser.add_argument("--intelligence-root", default=None, help="Optional root for persisted deterministic intelligence events")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    query = load_acceptance_query(args.query)
    output_dir = Path(args.output_dir)
    fixture_root = Path(args.fixture_root) if args.fixture_root else output_dir / "fixtures"
    intelligence_root = Path(args.intelligence_root) if args.intelligence_root else output_dir / "intelligence"
    artifact_set = run_acceptance(query, output_dir=output_dir, fixture_root=fixture_root, intelligence_root=intelligence_root)
    print(
        json.dumps(
            {
                "run_id": artifact_set.run_id,
                "output_dir": output_dir.as_posix(),
                "validation_passed": artifact_set.validation_passed,
                "optimization_proposed": artifact_set.optimization_proposed,
            },
            indent=2,
            sort_keys=True,
        )
    )


def run_acceptance(
    query: AcceptanceQuery,
    *,
    output_dir: Path,
    fixture_root: Path,
    intelligence_root: Path,
) -> AcceptanceArtifactSet:
    output_dir.mkdir(parents=True, exist_ok=True)
    helper = Phase17ReportHelper(output_dir)
    _ = helper.save_query_echo(query.model_dump())

    strategy = get_strategy(query.strategy_name)
    params = strategy.validate_params({})

    ohlcv_frame, ohlcv_meta = _prepare_ohlcv_fixture(query, params, fixture_root=fixture_root)
    feature_frame = strategy.build_features(ohlcv_frame, params)
    baseline_signal_frame = strategy.build_signals(ohlcv_frame, params)

    intelligence_events, context_frame = _prepare_intelligence_context(
        query,
        ohlcv_frame,
        intelligence_root=intelligence_root,
    )
    gate_ready_context = _prepare_gate_ready_context(context_frame)

    candidate_signal_frame = apply_context_gate_to_signals(
        baseline_signal_frame,
        gate_ready_context,
        max_spread_bps=query.context_gate.max_spread_bps,
        min_depth_imbalance=query.context_gate.min_depth_imbalance,
        max_depth_imbalance=query.context_gate.max_depth_imbalance,
        suppress_when_context_missing=True,
    )
    _assert_pre_gating_equivalence(baseline_signal_frame, candidate_signal_frame)

    backtester = PolarsSignalBacktester(initial_capital=1.0)
    baseline_result = backtester.run(baseline_signal_frame)
    candidate_result = backtester.run(candidate_signal_frame)

    _assert_one_bar_signal_lag(baseline_result.frame)
    _assert_one_bar_signal_lag(candidate_result.frame)

    baseline_joined = _attach_context_frame(baseline_result.frame, context_frame)
    candidate_joined = _attach_context_frame(candidate_result.frame, context_frame)
    _assert_backward_only_join(baseline_joined)
    _assert_backward_only_join(candidate_joined)

    baseline_validation = validate_metrics(baseline_result.metrics)
    candidate_validation = validate_metrics(candidate_result.metrics)
    baseline_summary = _build_run_summary(
        label="baseline",
        frame=baseline_result.frame,
        metrics=baseline_result.metrics,
        validation=baseline_validation,
    )
    candidate_summary = _build_run_summary(
        label="candidate",
        frame=candidate_result.frame,
        metrics=candidate_result.metrics,
        validation=candidate_validation,
    )

    optimization_request_path: Path | None = None
    if query.artifact_mode == "proposed_only":
        optimization_request_path = helper.save_optimization_request(
            _build_proposed_optimization_record(query, ohlcv_frame)
        )

    _write_json(output_dir / "ohlcv_snapshot.json", _frame_payload(ohlcv_frame))
    _write_json(output_dir / "feature_snapshot.json", _frame_payload(feature_frame))
    _write_json(output_dir / "intelligence_events.json", _frame_payload(intelligence_events))
    _write_json(output_dir / "context_frame.json", _frame_payload(context_frame))
    _write_json(output_dir / "joined_context_frame.json", _frame_payload(candidate_joined))
    _write_json(output_dir / "baseline_backtest.json", baseline_summary)
    _write_json(output_dir / "candidate_backtest.json", candidate_summary)

    validation_summary = _build_validation_summary(
        baseline_validation=baseline_validation,
        candidate_validation=candidate_validation,
        baseline_summary=baseline_summary,
        candidate_summary=candidate_summary,
        candidate_joined=candidate_joined,
        query=query,
    )
    _write_json(output_dir / "validation_summary.json", validation_summary)

    artifact_set = AcceptanceArtifactSet(
        run_id=_run_id(query),
        output_dir=".",
        query_echo=_sanitize(query.model_dump()),
        ohlcv_snapshot_meta=_sanitize(ohlcv_meta),
        intelligence_event_count=int(intelligence_events.height),
        joined_context_rows=int(candidate_joined.filter(pl.col("context_timestamp").is_not_null()).height),
        baseline_summary=baseline_summary,
        candidate_summary=candidate_summary,
        validation_passed=bool(validation_summary["validation_passed"]),
        validation_critique=str(validation_summary["validation_critique"]),
        optimization_proposed=optimization_request_path is not None,
        optimization_request_path=optimization_request_path.name if optimization_request_path else None,
    )
    _ = helper.save_artifact_set(artifact_set)
    _ = helper.write_markdown_report(artifact_set)
    return artifact_set


def _prepare_ohlcv_fixture(query: AcceptanceQuery, params: Any, *, fixture_root: Path) -> tuple[pl.DataFrame, dict[str, Any]]:
    seed_path = save_phase17_btc_ohlcv_fixture(root=fixture_root, symbol=DEFAULT_PHASE17_SYMBOL, timeframe="1m")
    seed_frame = load_phase17_btc_ohlcv_fixture(seed_path)
    expanded = _expand_seed_fixture(
        seed_frame,
        symbol=DEFAULT_PHASE17_SYMBOL,
        timeframe=query.timeframe,
        bars=_required_bar_count(params, timeframe=query.timeframe),
    )
    ohlcv_frame = validate_ohlcv(expanded)
    return ohlcv_frame, {
        "artifact_path": seed_path.name,
        "seed_fixture_path": seed_path.name,
        "rows": int(ohlcv_frame.height),
        "symbol": DEFAULT_PHASE17_SYMBOL,
        "query_symbol": query.symbol,
        "timeframe": query.timeframe,
        "start": ohlcv_frame.select(pl.col("timestamp").min()).item(),
        "end": ohlcv_frame.select(pl.col("timestamp").max()).item(),
    }


def _expand_seed_fixture(seed_frame: pl.DataFrame, *, symbol: str, timeframe: str, bars: int) -> pl.DataFrame:
    interval = _timeframe_delta(timeframe)
    timestamps = [seed_frame["timestamp"][0] + (interval * index) for index in range(bars)]
    seed_closes = [float(value) for value in seed_frame.get_column("close").to_list()]
    base_close = seed_closes[0]
    closes = _build_minute_fixture_closes(base_close, bars) if timeframe == "1m" else _build_hourly_fixture_closes(seed_closes, base_close, bars)
    opens = [closes[0], *closes[:-1]]
    highs = [round(max(open_value, close_value) + 0.45 + (0.04 * ((index % 5) + 1)), 6) for index, (open_value, close_value) in enumerate(zip(opens, closes, strict=True))]
    lows = [round(min(open_value, close_value) - 0.45 - (0.03 * ((index % 3) + 1)), 6) for index, (open_value, close_value) in enumerate(zip(opens, closes, strict=True))]
    volumes = [round(20.0 + (index % 11) * 1.7 + abs(math.sin(index / 5.0)) * 2.5, 6) for index in range(bars)]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "symbol": [symbol] * bars,
            "timeframe": [timeframe] * bars,
        }
    )


def _build_minute_fixture_closes(base_close: float, bars: int) -> list[float]:
    closes: list[float] = []
    price = base_close + 20.0
    recovery_bars = {111, 112, 113}
    profitable_exit_window = {210, 211, 212, 213, 214}
    for index in range(bars):
        if index < 120:
            price -= 0.08
        elif index < 150:
            price += 0.02
        else:
            price -= 0.01
        if index == 110:
            price -= 15.0
        elif index in recovery_bars:
            price += 3.75
        elif index in profitable_exit_window:
            price += 0.02
        closes.append(round(price, 6))
    return closes


def _build_hourly_fixture_closes(seed_closes: list[float], base_close: float, bars: int) -> list[float]:
    closes: list[float] = []
    for index in range(bars):
        motif = seed_closes[index % len(seed_closes)] - base_close
        trend = 0.07 * index
        seasonal = 3.8 * math.sin(index / 7.0) + 1.9 * math.sin(index / 19.0)
        pulse = 3.0 if index % 53 == 0 else (-4.0 if index % 53 == 6 else 0.0)
        closes.append(round(base_close + motif + trend + seasonal + pulse, 6))
    return closes


def _required_bar_count(params: Any, *, timeframe: str) -> int:
    integer_fields = [value for value in params.model_dump().values() if isinstance(value, int)]
    warmup = max(integer_fields, default=20)
    minimum = 240 if timeframe == "1m" else 320
    return max(warmup * 2, minimum)


def _prepare_intelligence_context(
    query: AcceptanceQuery,
    ohlcv_frame: pl.DataFrame,
    *,
    intelligence_root: Path,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    start = ohlcv_frame.select(pl.col("timestamp").min()).item()
    end = ohlcv_frame.select(pl.col("timestamp").max()).item()
    _ = save_phase17_intelligence_events(root=intelligence_root, symbol=DEFAULT_PHASE17_SYMBOL)
    _ = save_events(_build_extended_context_events(ohlcv_frame), root=intelligence_root)
    events = load_phase17_intelligence_events(
        start=start,
        end=end,
        root=intelligence_root,
        symbol=DEFAULT_PHASE17_SYMBOL,
    )
    context_frame = build_context_frame(
        DEFAULT_PHASE17_SYMBOL,
        start,
        end,
        query.timeframe,
        root=intelligence_root.as_posix(),
    )
    return events, _annotate_context_frame(context_frame, query)


def _build_extended_context_events(ohlcv_frame: pl.DataFrame) -> list[SignalEvent]:
    timestamps = ohlcv_frame.get_column("timestamp").to_list()
    events: list[SignalEvent] = []
    for index, timestamp in enumerate(timestamps):
        if index < 4:
            continue
        funding_rate = round(0.00016 * math.sin(index / 13.0), 8)
        spread_bps = round(10.0 + 5.5 * (1.0 + math.sin(index / 11.0)), 6)
        depth_imbalance = round(0.42 * math.sin(index / 9.0), 6)
        liquidation_imbalance = round(-0.55 if index % 37 in {0, 1, 2} else 0.35 * math.sin(index / 7.0), 6)
        open_interest = round(1_000_000.0 + index * 750.0, 6)
        events.extend(
            [
                SignalEvent(
                    source="okx_funding",
                    signal_type="funding_rate",
                    symbol=DEFAULT_PHASE17_SYMBOL,
                    timestamp=timestamp,
                    value=funding_rate,
                    metadata={"fixture": "phase17"},
                ),
                SignalEvent(
                    source="okx_orderbook",
                    signal_type="spread_bps",
                    symbol=DEFAULT_PHASE17_SYMBOL,
                    timestamp=timestamp,
                    value=spread_bps,
                    metadata={"fixture": "phase17"},
                ),
                SignalEvent(
                    source="okx_orderbook",
                    signal_type="depth_imbalance",
                    symbol=DEFAULT_PHASE17_SYMBOL,
                    timestamp=timestamp,
                    value=depth_imbalance,
                    metadata={"fixture": "phase17"},
                ),
                SignalEvent(
                    source="liquidations",
                    signal_type="liquidation_imbalance",
                    symbol=DEFAULT_PHASE17_SYMBOL,
                    timestamp=timestamp,
                    value=liquidation_imbalance,
                    metadata={"fixture": "phase17"},
                ),
                SignalEvent(
                    source="open_interest",
                    signal_type="open_interest",
                    symbol=DEFAULT_PHASE17_SYMBOL,
                    timestamp=timestamp,
                    value=open_interest,
                    metadata={"fixture": "phase17"},
                ),
            ]
        )
    return events


def _annotate_context_frame(context_frame: pl.DataFrame, query: AcceptanceQuery) -> pl.DataFrame:
    if context_frame.is_empty():
        return pl.DataFrame(
            {
                "timestamp": [],
                "symbol": [],
                "context_tags": [],
                "required_context_tags_pass": [],
            }
        )
    rows = context_frame.sort("timestamp").to_dicts()
    annotated_rows: list[dict[str, Any]] = []
    required_tags = query.context_gate.required_context_tags
    for row in rows:
        tags = _derive_context_tags(row)
        row["context_tags"] = tags
        row["required_context_tags_pass"] = all(tag in tags for tag in required_tags)
        annotated_rows.append(row)
    return pl.from_dicts(annotated_rows)


def _derive_context_tags(row: dict[str, Any]) -> list[str]:
    funding_rate = float(row.get("funding_rate") or 0.0)
    spread_bps = float(row.get("spread_bps") or 0.0)
    liquidation_imbalance = float(row.get("liquidation_imbalance") or 0.0)
    tags: list[str] = []
    if abs(funding_rate) >= 0.0001:
        tags.append("funding_extreme")
    if liquidation_imbalance <= -0.25 or funding_rate <= -0.00008:
        tags.append("risk_off")
    if spread_bps >= 12.0:
        tags.append("thin_liquidity")
    return tags


def _prepare_gate_ready_context(context_frame: pl.DataFrame) -> pl.DataFrame:
    if context_frame.is_empty():
        return context_frame
    return context_frame.with_columns(
        [
            pl.col("spread_bps").alias("raw_spread_bps") if "spread_bps" in context_frame.columns else pl.lit(None).alias("raw_spread_bps"),
            pl.col("depth_imbalance").alias("raw_depth_imbalance") if "depth_imbalance" in context_frame.columns else pl.lit(None).alias("raw_depth_imbalance"),
        ]
    ).with_columns(
        [
            pl.when(pl.col("required_context_tags_pass")).then(pl.col("spread_bps")).otherwise(None).alias("spread_bps")
            if "spread_bps" in context_frame.columns
            else pl.lit(None).alias("spread_bps"),
            pl.when(pl.col("required_context_tags_pass")).then(pl.col("depth_imbalance")).otherwise(None).alias("depth_imbalance")
            if "depth_imbalance" in context_frame.columns
            else pl.lit(None).alias("depth_imbalance"),
        ]
    )


def _attach_context_frame(frame: pl.DataFrame, context_frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    if context_frame.is_empty():
        return frame.sort("timestamp").with_columns(pl.lit(None).alias("context_timestamp"))
    rename_map = {
        column: ("context_timestamp" if column == "timestamp" else f"context_{column}")
        for column in context_frame.columns
    }
    right = context_frame.sort("timestamp").rename(rename_map)
    return frame.sort("timestamp").join_asof(right, left_on="timestamp", right_on="context_timestamp", strategy="backward")


def _assert_pre_gating_equivalence(baseline_signal_frame: pl.DataFrame, candidate_signal_frame: pl.DataFrame) -> None:
    baseline_signals = baseline_signal_frame.get_column("signal").to_list()
    candidate_raw = candidate_signal_frame.get_column("raw_signal").to_list()
    if baseline_signals != candidate_raw:
        raise ValueError("candidate raw_signal must match baseline pre-gating signal stream")


def _assert_one_bar_signal_lag(frame: pl.DataFrame) -> None:
    if frame.is_empty():
        return
    expected = frame.select(pl.col("target_position").shift(1).fill_null(0.0)).to_series().to_list()
    actual = frame.get_column("position").to_list()
    if actual != expected:
        raise ValueError("backtester position stream violates one-bar signal lag semantics")


def _assert_backward_only_join(frame: pl.DataFrame) -> None:
    if frame.is_empty() or "context_timestamp" not in frame.columns:
        return
    leaked_rows = frame.filter(pl.col("context_timestamp").is_not_null() & (pl.col("context_timestamp") > pl.col("timestamp")))
    if not leaked_rows.is_empty():
        raise ValueError("context join leaked future information")


def _build_run_summary(*, label: str, frame: pl.DataFrame, metrics: dict[str, Any], validation: ValidationResult) -> dict[str, Any]:
    signal_count = int(frame.filter(pl.col("signal").is_not_null()).height) if "signal" in frame.columns else 0
    entry_count = int(frame.filter(pl.col("signal") == 1).height) if "signal" in frame.columns else 0
    exit_count = int(frame.filter(pl.col("signal") == 0).height) if "signal" in frame.columns else 0
    suppressed_entries = int(frame.filter(pl.col("raw_signal") == 1).height - entry_count) if "raw_signal" in frame.columns else 0
    return _sanitize(
        {
            "label": label,
            "rows": int(frame.height),
            "signal_count": signal_count,
            "entry_count": entry_count,
            "exit_count": exit_count,
            "suppressed_entries": suppressed_entries,
            "trade_count": _estimate_trade_count(frame),
            "metrics": metrics,
            "validation": {
                "passed": validation.passed,
                "reasons": validation.reasons,
            },
        }
    )


def _estimate_trade_count(frame: pl.DataFrame) -> int:
    if frame.is_empty() or "position" not in frame.columns:
        return 0
    transitions = frame.with_columns((pl.col("position") > 0.0).cast(pl.Int8).alias("is_exposed"))
    entries = transitions.filter((pl.col("is_exposed") == 1) & (pl.col("is_exposed").shift(1).fill_null(0) == 0))
    return int(entries.height)


def _build_validation_summary(
    *,
    baseline_validation: ValidationResult,
    candidate_validation: ValidationResult,
    baseline_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    candidate_joined: pl.DataFrame,
    query: AcceptanceQuery,
) -> dict[str, Any]:
    suppressed_entries = int(candidate_summary.get("suppressed_entries", 0))
    joined_rows = int(candidate_joined.filter(pl.col("context_timestamp").is_not_null()).height)
    critique_parts = [
        f"Baseline validation passed={baseline_validation.passed}; candidate validation passed={candidate_validation.passed}.",
        f"Candidate context gating suppressed {suppressed_entries} entry bars after strategy signal generation.",
        f"Backward-only context attachment produced {joined_rows} joined bar rows for {query.strategy_name}.",
    ]
    if baseline_validation.reasons:
        critique_parts.append(f"Baseline contract notes: {', '.join(baseline_validation.reasons)}.")
    if candidate_validation.reasons:
        critique_parts.append(f"Candidate contract notes: {', '.join(candidate_validation.reasons)}.")
    return _sanitize(
        {
            "validation_passed": baseline_validation.passed and candidate_validation.passed,
            "validation_critique": " ".join(critique_parts),
            "baseline_validation": baseline_validation.model_dump(),
            "candidate_validation": candidate_validation.model_dump(),
            "metric_deltas": _metric_deltas(
                baseline_summary.get("metrics", {}),
                candidate_summary.get("metrics", {}),
            ),
            "required_context_tags": query.context_gate.required_context_tags,
        }
    )


def _metric_deltas(baseline_metrics: dict[str, Any], candidate_metrics: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key, baseline_value in baseline_metrics.items():
        candidate_value = candidate_metrics.get(key)
        if isinstance(baseline_value, (int, float)) and isinstance(candidate_value, (int, float)):
            deltas[key] = float(candidate_value) - float(baseline_value)
    return deltas


def _build_proposed_optimization_request(query: AcceptanceQuery, ohlcv_frame: pl.DataFrame) -> OptimizationRequest:
    midpoint = max(1, ohlcv_frame.height // 2)
    timestamps = ohlcv_frame.get_column("timestamp").to_list()
    train_period = f"{timestamps[0].isoformat()} to {timestamps[midpoint - 1].isoformat()}"
    test_period = f"{timestamps[midpoint].isoformat()} to {timestamps[-1].isoformat()}"
    return OptimizationRequest(
        strategy_name=query.strategy_name,
        symbols=[query.symbol],
        timeframes=[query.timeframe],
        train_period=train_period,
        test_period=test_period,
        acceptance_criteria=AcceptanceCriteria(),
        created_by="workflow",
        source_event_id=_run_id(query),
        context_filters=query.context_gate.model_dump(),
    )


def _build_proposed_optimization_record(query: AcceptanceQuery, ohlcv_frame: pl.DataFrame) -> OptimizationRequestRecord:
    request = _build_proposed_optimization_request(query, ohlcv_frame)
    created_at = ohlcv_frame.get_column("timestamp").to_list()[0]
    return OptimizationRequestRecord(
        request_id=f"{_run_id(query)}-proposed",
        request_payload=request.model_dump(),
        created_by=request.created_by,
        created_at=created_at,
    )


def _frame_payload(frame: pl.DataFrame) -> dict[str, Any]:
    return _sanitize(
        {
            "schema": {column: str(dtype) for column, dtype in frame.schema.items()},
            "rows": frame.sort(frame.columns[0]).to_dicts() if frame.columns else [],
        }
    )


def _run_id(query: AcceptanceQuery) -> str:
    return f"phase17-{query.strategy_name}-{query.symbol.lower()}-{query.timeframe}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize(payload), indent=2, sort_keys=True, default=_json_default), encoding="utf-8")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _timeframe_delta(timeframe: str) -> timedelta:
    if timeframe == "1m":
        return timedelta(minutes=1)
    if timeframe == "1h":
        return timedelta(hours=1)
    raise ValueError(f"unsupported timeframe: {timeframe}")


if __name__ == "__main__":
    main()
