"""Local parquet storage for intelligence events."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import polars as pl

from quant_stack.intelligence.schemas import SignalEvent


DEFAULT_INTELLIGENCE_ROOT = Path("data/intelligence/okx")


def events_to_frame(events: list[SignalEvent]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "source": [event.source for event in events],
            "signal_type": [event.signal_type for event in events],
            "symbol": [event.symbol for event in events],
            "timestamp": [event.timestamp for event in events],
            "value": [event.value for event in events],
            "historical_integrity": [event.historical_integrity for event in events],
            "metadata": [json.dumps(event.metadata, sort_keys=True) for event in events],
        }
    )


def save_events(events: list[SignalEvent], *, root: str | Path = DEFAULT_INTELLIGENCE_ROOT) -> list[Path]:
    if not events:
        return []
    frame = events_to_frame(events).with_columns(pl.col("timestamp").dt.date().alias("date"))
    paths: list[Path] = []
    for row in frame.select(["source", "symbol", "date"]).unique().iter_rows(named=True):
        source = str(row["source"])
        symbol = str(row["symbol"])
        date = row["date"]
        partition = frame.filter((pl.col("source") == source) & (pl.col("symbol") == symbol) & (pl.col("date") == date)).drop("date")
        date_str = str(date)
        path = Path(root) / f"source={source}" / f"symbol={symbol}" / f"date={date_str}" / "events.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        partition.write_parquet(path)
        paths.append(path)
    return paths


def load_events(
    *,
    symbol: str,
    start: datetime,
    end: datetime,
    root: str | Path = DEFAULT_INTELLIGENCE_ROOT,
) -> pl.DataFrame:
    base = Path(root)
    if not base.exists():
        return pl.DataFrame(
            schema={
                "source": pl.Utf8,
                "signal_type": pl.Utf8,
                "symbol": pl.Utf8,
                "timestamp": pl.Datetime(time_zone="UTC"),
                "value": pl.Float64,
                "historical_integrity": pl.Boolean,
                "metadata": pl.Object,
            }
        )
    files = list(base.glob(f"source=*/symbol={symbol}/date=*/events.parquet"))
    if not files:
        return pl.DataFrame(
            {
                "source": [],
                "signal_type": [],
                "symbol": [],
                "timestamp": [],
                "value": [],
                "historical_integrity": [],
                "metadata": [],
            }
        )
    frame = pl.concat([pl.read_parquet(path) for path in files], how="vertical_relaxed")
    return frame.filter((pl.col("timestamp") >= pl.lit(start)) & (pl.col("timestamp") <= pl.lit(end))).sort("timestamp")


__all__ = ["DEFAULT_INTELLIGENCE_ROOT", "events_to_frame", "load_events", "save_events"]
