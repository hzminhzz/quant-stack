from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

from quant_stack.data.datasets import BybitDatasetConfig, build_bybit_market_dataset
from quant_stack.data.derivatives import download_bybit_funding, download_bybit_open_interest
from quant_stack.data.derivatives.store import store_bybit_funding, store_bybit_open_interest
from quant_stack.data.ohlcv import download_bybit_ohlcv
from quant_stack.data.ohlcv.store import store_bybit_ohlcv
from quant_stack.features import FeaturePipelineConfig, FeatureWindowConfig, build_feature_dataset
from quant_stack.research.experiments.runner import run_strategy_experiment
from quant_stack.research.experiments.schemas import ExperimentConfig
from quant_stack.strategies import get_strategy


REQUIRED_FEATURE_COLUMNS = [
    "timestamp",
    "available_at",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rsi_14",
    "funding_zscore_30",
    "momentum_slope_10",
    "price_extension_20",
    "ret_60",
]


@dataclass
class ScanResult:
    perp_ohlcv: Path
    spot_ohlcv: Path
    funding: Path
    open_interest: Path
    market_dataset: Path
    feature_dataset: Path


def _parse_date(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _scan_paths(symbol: str, timeframe: str) -> ScanResult:
    return ScanResult(
        perp_ohlcv=Path(f"data/ohlcv/bybit/linear/{timeframe}/{symbol}.parquet"),
        spot_ohlcv=Path(f"data/ohlcv/bybit/spot/{timeframe}/{symbol}.parquet"),
        funding=Path(f"data/derivatives/bybit/funding/{symbol}.parquet"),
        open_interest=Path(f"data/derivatives/bybit/open_interest/{symbol}.parquet"),
        market_dataset=Path(f"data/datasets/bybit/market/{symbol}/{timeframe}/market_dataset.parquet"),
        feature_dataset=Path(f"data/features/bybit/{symbol}/{timeframe}/features.parquet"),
    )


def _path_covers_window(path: Path, *, start: datetime, end: datetime) -> bool:
    if not path.exists():
        return False
    df = pl.read_parquet(path)
    if df.is_empty() or "timestamp" not in df.columns:
        return False
    actual_start = df.select(pl.col("timestamp").min()).item()
    actual_end = df.select(pl.col("timestamp").max()).item()
    return bool(actual_start <= start and actual_end >= end)


def _ensure_raw_data(scan: ScanResult, symbol: str, timeframe: str, start: datetime, end: datetime) -> None:
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    if not _path_covers_window(scan.perp_ohlcv, start=start, end=end):
        perp = download_bybit_ohlcv(symbol, market_type="linear", timeframe=timeframe, start_time_ms=start_ms, end_time_ms=end_ms)
        store_bybit_ohlcv(perp, symbol=symbol, market_type="linear", timeframe=timeframe)

    if not _path_covers_window(scan.spot_ohlcv, start=start, end=end):
        spot = download_bybit_ohlcv(symbol, market_type="spot", timeframe=timeframe, start_time_ms=start_ms, end_time_ms=end_ms)
        store_bybit_ohlcv(spot, symbol=symbol, market_type="spot", timeframe=timeframe)

    if not _path_covers_window(scan.funding, start=start, end=end):
        funding = download_bybit_funding(symbol, category="linear", start_time_ms=start_ms, end_time_ms=end_ms)
        store_bybit_funding(funding, symbol=symbol)

    if not _path_covers_window(scan.open_interest, start=start, end=end):
        oi = download_bybit_open_interest(
            symbol,
            category="linear",
            interval_time="5min",
            start_time_ms=start_ms,
            end_time_ms=end_ms,
        )
        store_bybit_open_interest(oi, symbol=symbol)


def _build_market_dataset(symbol: str, timeframe: str, start: datetime, end: datetime) -> Path:
    result = build_bybit_market_dataset(
        BybitDatasetConfig(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            output_dir="data/datasets/bybit/market",
            require_spot=True,
            require_funding=True,
            require_open_interest=True,
        )
    )
    built = Path(result.dataset_path)
    target = built.parent / "market_dataset.parquet"
    pl.read_parquet(built).write_parquet(target)
    return target


def _build_features(market_dataset_path: Path, out_path: Path) -> Path:
    df = pl.read_parquet(market_dataset_path)
    features = build_feature_dataset(
        df,
        config=FeaturePipelineConfig(
            timeframe="1m",
            allow_missing_derivatives=False,
            enforce_single_symbol=True,
            allow_panel=False,
            strict_derivative_causality=False,
        ),
        windows=FeatureWindowConfig(),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.write_parquet(out_path)
    return out_path


def _coverage_after_warmup(df: pl.DataFrame, column: str, warmup_rows: int = 120) -> float:
    if column not in df.columns:
        return 0.0
    sliced = df.slice(min(warmup_rows, df.height))
    if sliced.height == 0:
        return 0.0
    non_null = sliced.filter(pl.col(column).is_not_null()).height
    return float(non_null / sliced.height)


def _run_qa(features_path: Path, qa_report_path: Path) -> dict[str, object]:
    df = pl.read_parquet(features_path).sort("timestamp")
    required_missing = sorted(set(REQUIRED_FEATURE_COLUMNS) - set(df.columns))
    duplicate_timestamps = int(df.group_by("timestamp").len().filter(pl.col("len") > 1).height)
    sorted_ok = bool(df.get_column("timestamp").is_sorted())

    leakage_count = 0
    if "funding_available_at" in df.columns and "available_at" in df.columns:
        leakage_count += int(df.filter(pl.col("funding_available_at").is_not_null() & (pl.col("funding_available_at") > pl.col("available_at"))).height)
    if "oi_available_at" in df.columns and "available_at" in df.columns:
        leakage_count += int(df.filter(pl.col("oi_available_at").is_not_null() & (pl.col("oi_available_at") > pl.col("available_at"))).height)

    coverage = {
        "funding_zscore_30": _coverage_after_warmup(df, "funding_zscore_30"),
        "momentum_slope_10": _coverage_after_warmup(df, "momentum_slope_10"),
        "ret_60": _coverage_after_warmup(df, "ret_60"),
        "price_extension_20": _coverage_after_warmup(df, "price_extension_20"),
    }

    qa = {
        "readable": True,
        "row_count": int(df.height),
        "timestamp_sorted": sorted_ok,
        "duplicate_timestamps": duplicate_timestamps,
        "missing_required_columns": required_missing,
        "coverage_after_warmup": coverage,
        "availability_leakage_count": leakage_count,
        "start": str(df.select(pl.col("timestamp").min()).item()),
        "end": str(df.select(pl.col("timestamp").max()).item()),
        "columns": df.columns,
    }

    qa_report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Bybit BTCUSDT Feature Dataset QA",
        "",
        f"- readable: **{qa['readable']}**",
        f"- row_count: **{qa['row_count']}**",
        f"- timestamp_sorted: **{qa['timestamp_sorted']}**",
        f"- duplicate_timestamps: **{qa['duplicate_timestamps']}**",
        f"- availability_leakage_count: **{qa['availability_leakage_count']}**",
        f"- start: `{qa['start']}`",
        f"- end: `{qa['end']}`",
        "",
        "## Required column check",
        f"- missing_required_columns: `{qa['missing_required_columns']}`",
        "",
        "## Coverage after warmup",
    ]
    for key, value in coverage.items():
        lines.append(f"- {key}: **{value:.4f}**")
    lines.append("")
    lines.append("## Column list")
    for col in qa["columns"]:
        lines.append(f"- {col}")

    qa_report_path.write_text("\n".join(lines), encoding="utf-8")
    return qa


def _readiness_check(features_path: Path, symbol: str, timeframe: str) -> dict[str, object]:
    df = pl.read_parquet(features_path).sort("timestamp")
    strategy = get_strategy("funding_exhaustion_reversal")

    baseline_params = strategy.validate_params(
        {
            "use_context_filters": False,
            "require_price_extension": True,
            "require_momentum_turn": True,
            "require_basis_confirmation": False,
            "exit_on_rsi_midline": True,
        }
    )
    context_params = strategy.validate_params(
        {
            "use_context_filters": True,
            "funding_zscore_threshold": 2.0,
            "require_price_extension": True,
            "require_momentum_turn": True,
            "require_basis_confirmation": False,
            "exit_on_rsi_midline": True,
        }
    )

    baseline_signals = strategy.build_signals(df, baseline_params)
    context_signals = strategy.build_signals(df, context_params)

    end = df.select(pl.col("timestamp").max()).item()
    start = end - timedelta(hours=6)

    smoke_out = Path("reports/experiments/funding_exhaustion_reversal/readiness_smoke")
    smoke_report = run_strategy_experiment(
        ExperimentConfig(
            strategy_name="funding_exhaustion_reversal",
            dataset_path=features_path.as_posix(),
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            baseline_params={
                "require_price_extension": True,
                "require_momentum_turn": True,
                "require_basis_confirmation": False,
                "exit_on_rsi_midline": True,
            },
            context_params={
                "funding_zscore_threshold": 2.0,
                "require_price_extension": True,
                "require_momentum_turn": True,
                "require_basis_confirmation": False,
                "exit_on_rsi_midline": True,
            },
            fee_bps=0.0,
            slippage_bps=0.0,
            output_dir=smoke_out.as_posix(),
        )
    )

    return {
        "baseline_signal_generation_ok": baseline_signals.height > 0,
        "context_signal_generation_ok": context_signals.height > 0,
        "harness_tiny_slice_ok": True,
        "harness_tiny_slice_output_dir": smoke_out.as_posix(),
        "harness_verdict": smoke_report.verdict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 18G build for Bybit BTCUSDT feature dataset")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--start", default="2024-01-01T00:00:00+00:00")
    parser.add_argument("--end", default="2024-03-01T00:00:00+00:00")
    args = parser.parse_args()

    symbol = args.symbol
    timeframe = args.timeframe
    start = _parse_date(args.start)
    end = _parse_date(args.end)

    scan = _scan_paths(symbol, timeframe)
    _ensure_raw_data(scan, symbol, timeframe, start, end)

    market_dataset_path = _build_market_dataset(symbol, timeframe, start, end)
    features_path = _build_features(market_dataset_path, scan.feature_dataset)

    qa_report_path = Path("reports/data/bybit_btcusdt_feature_dataset_qa.md")
    qa = _run_qa(features_path, qa_report_path)
    readiness = _readiness_check(features_path, symbol, timeframe)

    summary = {
        "raw_paths": {
            "perp_ohlcv": scan.perp_ohlcv.as_posix(),
            "spot_ohlcv": scan.spot_ohlcv.as_posix(),
            "funding": scan.funding.as_posix(),
            "open_interest": scan.open_interest.as_posix(),
        },
        "dataset_built_path": market_dataset_path.as_posix(),
        "feature_parquet_path": features_path.as_posix(),
        "qa_report_path": qa_report_path.as_posix(),
        "qa": qa,
        "readiness": readiness,
        "phase18f_full_rerun_command": (
            "uv run python -m quant_stack.cli.run_strategy_experiment "
            "--strategy funding_exhaustion_reversal "
            f"--dataset {features_path.as_posix()} --symbol {symbol} --timeframe {timeframe} "
            "--start 2024-01-01T00:00:00+00:00 --end 2024-03-01T00:00:00+00:00 "
            "--baseline-params reports/experiments/funding_exhaustion_reversal/baseline_params.json "
            "--context-params reports/experiments/funding_exhaustion_reversal/context_params.json "
            "--output-dir reports/experiments/funding_exhaustion_reversal/full_run"
        ),
    }
    Path("reports/data").mkdir(parents=True, exist_ok=True)
    Path("reports/data/bybit_btcusdt_feature_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
