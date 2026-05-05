"""Snapshot and frame builders for intelligence context."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from quant_stack.intelligence.schemas import MarketContextSnapshot
from quant_stack.intelligence.store import load_events


SIGNAL_MAP: dict[str, str] = {
    "funding_rate": "funding_rate",
    "open_interest": "open_interest",
    "basis_bps": "basis_bps",
    "spread_bps": "spread_bps",
    "depth_imbalance": "depth_imbalance",
    "liquidation_imbalance": "liquidation_imbalance",
}


def build_context_snapshot(symbol: str, timestamp: datetime, *, root: str = "data/intelligence/okx") -> MarketContextSnapshot:
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    frame = load_events(symbol=symbol, start=datetime(1970, 1, 1, tzinfo=timezone.utc), end=ts, root=root)
    if frame.is_empty():
        return MarketContextSnapshot(symbol=symbol, timestamp=ts, unavailable_signals=list(SIGNAL_MAP.values()))

    valid = frame.filter(pl.col("timestamp") <= pl.lit(ts))
    unavailable: list[str] = []
    values: dict[str, float | None] = {}
    for signal_type, field_name in SIGNAL_MAP.items():
        subset = valid.filter((pl.col("signal_type") == signal_type) & (pl.col("historical_integrity") == True)).sort("timestamp")
        if subset.is_empty():
            unavailable.append(field_name)
            values[field_name] = None
        else:
            values[field_name] = float(subset.select(pl.col("value").last()).item())
    return MarketContextSnapshot(
        symbol=symbol,
        timestamp=ts,
        funding_rate=values.get("funding_rate"),
        open_interest=values.get("open_interest"),
        basis_bps=values.get("basis_bps"),
        spread_bps=values.get("spread_bps"),
        depth_imbalance=values.get("depth_imbalance"),
        liquidation_imbalance=values.get("liquidation_imbalance"),
        unavailable_signals=unavailable,
    )


def build_context_frame(symbol: str, start: datetime, end: datetime, timeframe: str, *, root: str = "data/intelligence/okx") -> pl.DataFrame:
    frame = load_events(symbol=symbol, start=start, end=end, root=root)
    if frame.is_empty():
        return pl.DataFrame({"timestamp": [], "symbol": []})

    pivot = (
        frame.filter(pl.col("historical_integrity") == True)
        .group_by(["timestamp", "signal_type"]) 
        .agg(pl.col("value").last().alias("value"))
        .pivot(index="timestamp", on="signal_type", values="value")
        .sort("timestamp")
    )
    if "symbol" not in pivot.columns:
        pivot = pivot.with_columns(pl.lit(symbol).alias("symbol"))

    # Keep as-of safety: forward-fill only from past rows.
    filled = pivot.sort("timestamp").with_columns([pl.col(column).forward_fill() for column in pivot.columns if column not in {"timestamp", "symbol"}])
    return filled


def join_context_to_trades(trades_df: pl.DataFrame, context_df: pl.DataFrame) -> pl.DataFrame:
    if trades_df.is_empty() or context_df.is_empty():
        return trades_df
    left = trades_df.sort("timestamp")
    right = context_df.sort("timestamp")
    return left.join_asof(right, on="timestamp", strategy="backward")


__all__ = ["build_context_frame", "build_context_snapshot", "join_context_to_trades"]
