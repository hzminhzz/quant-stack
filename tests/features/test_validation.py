from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from quant_stack.features.validation import check_derivative_causality, check_single_symbol_timeframe, validate_feature_input


def _base() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)],
            "available_at": [datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc)],
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [10.0, 11.0],
        }
    )


def test_missing_required_detected() -> None:
    report = validate_feature_input(_base().drop("close"))
    assert report.passed is False


def test_duplicate_and_non_monotonic_detected() -> None:
    report_dup = validate_feature_input(pl.concat([_base(), _base().head(1)], how="vertical"))
    assert report_dup.passed is False

    report_order = validate_feature_input(_base().reverse())
    assert report_order.passed is False


def test_single_symbol_panel_checks() -> None:
    df = _base().with_columns(pl.lit("BTCUSDT").alias("symbol"), pl.lit("1m").alias("timeframe"))
    panel, symbol_count, timeframe_count = check_single_symbol_timeframe(df)
    assert panel is False
    assert symbol_count == 1
    assert timeframe_count == 1


def test_derivative_causality_rules() -> None:
    base = _base().with_columns(
        [
            pl.lit(0.0).alias("funding_rate"),
            pl.col("available_at").alias("funding_available_at"),
            pl.lit(100.0).alias("open_interest"),
            pl.col("available_at").alias("oi_available_at"),
        ]
    )
    violations, errors, warnings = check_derivative_causality(base, strict=True)
    assert violations == 0
    assert errors == []
    assert warnings == []
