"""Validation utilities for feature-input and feature-output frames."""

from __future__ import annotations

import polars as pl

from quant_stack.features.schemas import FeatureValidationReport


def check_required_columns(df: pl.DataFrame, required_columns: list[str]) -> list[str]:
    return [col for col in required_columns if col not in df.columns]


def check_no_duplicate_timestamps(df: pl.DataFrame) -> int:
    if "timestamp" not in df.columns:
        return 0
    return int(df.height - df.select(pl.col("timestamp").n_unique()).item())


def check_timestamp_monotonic(df: pl.DataFrame) -> bool:
    if "timestamp" not in df.columns or df.height <= 1:
        return True
    timestamps = df.get_column("timestamp")
    return timestamps.to_list() == timestamps.sort().to_list()


def check_feature_nulls(df: pl.DataFrame, feature_columns: list[str]) -> dict[str, int]:
    present = [col for col in feature_columns if col in df.columns]
    if not present:
        return {}
    row = df.select([pl.col(col).null_count().alias(col) for col in present]).row(0, named=True)
    return {str(k): int(v) for k, v in row.items()}


def validate_feature_input(df: pl.DataFrame, require_derivatives: bool = False) -> FeatureValidationReport:
    required = ["timestamp", "available_at", "open", "high", "low", "close", "volume"]
    optional = ["funding_rate", "open_interest", "basis"]
    missing_required = check_required_columns(df, required)
    missing_optional = [col for col in optional if col not in df.columns]
    errors: list[str] = []
    warnings: list[str] = []
    if missing_required:
        errors.append("missing required columns")
    if require_derivatives and missing_optional:
        errors.append("missing required derivative columns")
    dup = check_no_duplicate_timestamps(df)
    if dup > 0:
        errors.append("duplicate timestamps detected")
    monotonic = check_timestamp_monotonic(df)
    if not monotonic:
        errors.append("timestamp is not monotonic ascending")

    return FeatureValidationReport(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        row_count=df.height,
        column_count=len(df.columns),
        missing_required_columns=missing_required,
        missing_optional_columns=missing_optional,
        null_feature_counts={},
        duplicate_timestamp_count=dup,
        non_monotonic_timestamp=not monotonic,
    )


def check_single_symbol_timeframe(df: pl.DataFrame) -> tuple[bool, int | None, int | None]:
    symbol_count: int | None = None
    timeframe_count: int | None = None
    panel = False
    if "symbol" in df.columns:
        symbol_count = int(df.select(pl.col("symbol").n_unique()).item())
        if symbol_count > 1:
            panel = True
    if "timeframe" in df.columns:
        timeframe_count = int(df.select(pl.col("timeframe").n_unique()).item())
        if timeframe_count > 1:
            panel = True
    return panel, symbol_count, timeframe_count


def check_derivative_causality(
    df: pl.DataFrame,
    *,
    strict: bool,
) -> tuple[int, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    violations = 0
    pairs = [
        ("funding_rate", "funding_available_at"),
        ("open_interest", "oi_available_at"),
        ("basis", "basis_available_at"),
    ]
    for value_col, avail_col in pairs:
        if value_col not in df.columns:
            continue
        if avail_col not in df.columns:
            if strict:
                errors.append(f"{value_col} present but {avail_col} missing under strict_derivative_causality")
            else:
                warnings.append(f"{value_col} present but {avail_col} missing")
            continue
        count = int(
            df.filter(pl.col(value_col).is_not_null() & pl.col(avail_col).is_not_null() & (pl.col(avail_col) > pl.col("available_at"))).height
        )
        violations += count
        if count > 0:
            msg = f"{value_col} causality violated in {count} rows ({avail_col} > available_at)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)
    return violations, errors, warnings


def validate_feature_output(df: pl.DataFrame) -> FeatureValidationReport:
    feature_cols = [col for col in df.columns if col not in {"timestamp", "available_at", "symbol", "timeframe", "open", "high", "low", "close", "volume"}]
    dup = check_no_duplicate_timestamps(df)
    monotonic = check_timestamp_monotonic(df)
    errors: list[str] = []
    if dup > 0:
        errors.append("duplicate timestamps detected")
    if not monotonic:
        errors.append("timestamp is not monotonic ascending")
    return FeatureValidationReport(
        passed=len(errors) == 0,
        errors=errors,
        warnings=[],
        row_count=df.height,
        column_count=len(df.columns),
        missing_required_columns=[],
        missing_optional_columns=[],
        null_feature_counts=check_feature_nulls(df, feature_cols),
        duplicate_timestamp_count=dup,
        non_monotonic_timestamp=not monotonic,
    )


def assert_no_future_columns(df: pl.DataFrame) -> None:
    forbidden = [col for col in df.columns if "future" in col.lower() or "lead" in col.lower()]
    if forbidden:
        raise ValueError(f"forbidden future-looking columns present: {', '.join(forbidden)}")


__all__ = [
    "assert_no_future_columns",
    "check_derivative_causality",
    "check_feature_nulls",
    "check_no_duplicate_timestamps",
    "check_required_columns",
    "check_single_symbol_timeframe",
    "check_timestamp_monotonic",
    "validate_feature_input",
    "validate_feature_output",
]
