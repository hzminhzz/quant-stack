"""Liquidation source schema utilities and local/mock loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from quant_stack.intelligence.normalize import liquidation_to_signal_events
from quant_stack.intelligence.schemas import SignalEvent


def load_liquidation_rows(path: str | Path) -> list[dict[str, Any]]:
    frame = pl.read_parquet(path) if str(path).endswith(".parquet") else pl.read_csv(path)
    required = {"symbol", "timestamp", "long_liquidation_notional", "short_liquidation_notional"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing liquidation columns: {', '.join(missing)}")
    return frame.to_dicts()


def liquidation_events_from_rows(rows: list[dict[str, Any]], *, historical_integrity: bool = False) -> list[SignalEvent]:
    return liquidation_to_signal_events(rows, historical_integrity=historical_integrity)


__all__ = ["liquidation_events_from_rows", "load_liquidation_rows"]
