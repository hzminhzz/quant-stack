from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl

from quant_stack.research.labeling import TripleBarrierConfig, triple_barrier_labels


def _price_frame() -> pl.DataFrame:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    close = [100.0, 101.0, 103.0, 99.0, 98.0, 102.0]
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=i) for i in range(len(close))],
            "open": close,
            "high": [c + 0.5 for c in close],
            "low": [c - 0.5 for c in close],
            "close": close,
        }
    )


def test_triple_barrier_labels_adds_expected_columns() -> None:
    frame = _price_frame()
    out = triple_barrier_labels(
        frame,
        TripleBarrierConfig(profit_take_pct=0.01, stop_loss_pct=0.01, max_holding_bars=2),
    )
    for col in ["label", "label_time", "label_price", "label_return", "label_bars", "barrier_hit"]:
        assert col in out.columns
    assert out.height == frame.height


def test_triple_barrier_labels_is_deterministic_and_sorted() -> None:
    frame = _price_frame().reverse()
    config = TripleBarrierConfig(profit_take_pct=0.015, stop_loss_pct=0.01, max_holding_bars=3)
    out1 = triple_barrier_labels(frame, config)
    out2 = triple_barrier_labels(frame, config)
    assert out1["timestamp"].to_list() == sorted(out1["timestamp"].to_list())
    assert out1["label"].to_list() == out2["label"].to_list()
    assert out1["label_time"].to_list() == out2["label_time"].to_list()


def test_triple_barrier_respects_group_boundaries() -> None:
    base = _price_frame()
    panel = pl.concat(
        [
            base.with_columns(pl.lit("BTCUSDT").alias("symbol")),
            base.with_columns(pl.lit("ETHUSDT").alias("symbol")),
        ]
    )
    out = triple_barrier_labels(
        panel,
        TripleBarrierConfig(
            profit_take_pct=0.01,
            stop_loss_pct=0.01,
            max_holding_bars=2,
            group_col="symbol",
        ),
    )
    assert out.group_by("symbol").len().sort("symbol")["len"].to_list() == [base.height, base.height]


def test_triple_barrier_horizon_expiry_sets_time_barrier() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc),
            ],
            "open": [100.0, 100.0, 100.0],
            "high": [100.1, 100.1, 100.1],
            "low": [99.9, 99.9, 99.9],
            "close": [100.0, 100.0, 100.0],
        }
    )
    out = triple_barrier_labels(
        frame,
        TripleBarrierConfig(profit_take_pct=0.05, stop_loss_pct=0.05, max_holding_bars=1),
    )
    assert out["barrier_hit"].to_list()[0] == "time"
    assert out["label"][0] == 0


def test_triple_barrier_same_bar_conflict_prefers_profit_take() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            ],
            "open": [100.0, 100.0],
            "high": [100.0, 102.0],
            "low": [100.0, 98.0],
            "close": [100.0, 100.0],
        }
    )
    out = triple_barrier_labels(
        frame,
        TripleBarrierConfig(profit_take_pct=0.01, stop_loss_pct=0.01, max_holding_bars=1),
    )
    assert out["barrier_hit"][0] == "profit_take"
    assert out["label"][0] == 1


def test_triple_barrier_duplicate_timestamps_deterministic() -> None:
    ts = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    frame = pl.DataFrame(
        {
            "timestamp": [ts, ts, ts + timedelta(minutes=1)],
            "open": [100.0, 100.0, 100.0],
            "high": [100.0, 101.5, 100.2],
            "low": [100.0, 99.5, 99.8],
            "close": [100.0, 100.2, 100.1],
        }
    )
    cfg = TripleBarrierConfig(profit_take_pct=0.01, stop_loss_pct=0.01, max_holding_bars=1)
    out1 = triple_barrier_labels(frame, cfg)
    out2 = triple_barrier_labels(frame, cfg)
    assert out1["label"].to_list() == out2["label"].to_list()


def test_triple_barrier_single_row_group_supported() -> None:
    frame = pl.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)],
            "symbol": ["BTCUSDT", "ETHUSDT"],
            "open": [100.0, 200.0],
            "high": [100.1, 200.1],
            "low": [99.9, 199.9],
            "close": [100.0, 200.0],
        }
    )
    out = triple_barrier_labels(
        frame,
        TripleBarrierConfig(profit_take_pct=0.01, stop_loss_pct=0.01, max_holding_bars=2, group_col="symbol"),
    )
    assert out.height == 2
    assert out["label_bars"].to_list() == [0, 0]


def test_triple_barrier_does_not_mutate_input_frame() -> None:
    frame = _price_frame()
    before_cols = list(frame.columns)
    before_values = frame.to_dicts()
    _ = triple_barrier_labels(
        frame,
        TripleBarrierConfig(profit_take_pct=0.01, stop_loss_pct=0.01, max_holding_bars=2),
    )
    assert frame.columns == before_cols
    assert frame.to_dicts() == before_values
