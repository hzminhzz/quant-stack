"""Normalization helpers for intelligence source payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from quant_stack.intelligence.schemas import SignalEvent


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper().replace("/", "-").replace("_", "-")
    if cleaned.endswith("-SWAP"):
        return cleaned
    if cleaned.count("-") == 1:
        base, quote = cleaned.split("-")
        return f"{base}-{quote}-SWAP"
    return cleaned


def normalize_timestamp(value: datetime | int | float | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # Accept epoch ms or seconds.
        if value > 10_000_000_000:
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def funding_to_signal_events(payload: list[dict[str, Any]], *, source: str = "okx_funding") -> list[SignalEvent]:
    events: list[SignalEvent] = []
    for row in payload:
        events.append(
            SignalEvent(
                source=source,
                signal_type="funding_rate",
                symbol=normalize_symbol(str(row["symbol"])),
                timestamp=normalize_timestamp(row["timestamp"]),
                value=float(row["funding_rate"]),
                metadata={"next_funding_time": row.get("next_funding_time")},
            )
        )
    return events


def open_interest_to_signal_events(payload: list[dict[str, Any]], *, source: str = "okx_open_interest") -> list[SignalEvent]:
    return [
        SignalEvent(
            source=source,
            signal_type="open_interest",
            symbol=normalize_symbol(str(row["symbol"])),
            timestamp=normalize_timestamp(row["timestamp"]),
            value=float(row["open_interest"]),
            metadata={"open_interest_usd": row.get("open_interest_usd")},
        )
        for row in payload
    ]


def basis_to_signal_events(payload: list[dict[str, Any]], *, source: str = "okx_basis") -> list[SignalEvent]:
    events: list[SignalEvent] = []
    for row in payload:
        spot = float(row["spot_price"])
        perp = float(row["perp_price"])
        basis = perp - spot
        basis_bps = (basis / spot) * 10_000.0 if spot != 0 else 0.0
        events.append(
            SignalEvent(
                source=source,
                signal_type="basis_bps",
                symbol=normalize_symbol(str(row["symbol"])),
                timestamp=normalize_timestamp(row["timestamp"]),
                value=basis_bps,
                metadata={"spot_price": spot, "perp_price": perp, "basis": basis},
            )
        )
    return events


def orderbook_to_signal_events(payload: list[dict[str, Any]], *, source: str = "okx_orderbook") -> list[SignalEvent]:
    events: list[SignalEvent] = []
    for row in payload:
        bid = float(row["best_bid"])
        ask = float(row["best_ask"])
        spread = ask - bid
        mid = (ask + bid) / 2.0 if (ask + bid) else 0.0
        spread_bps = (spread / mid) * 10_000.0 if mid else 0.0
        bid_depth = float(row["bid_depth"])
        ask_depth = float(row["ask_depth"])
        denom = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / denom if denom else 0.0
        ts = normalize_timestamp(row["timestamp"])
        symbol = normalize_symbol(str(row["symbol"]))
        events.extend(
            [
                SignalEvent(source=source, signal_type="spread_bps", symbol=symbol, timestamp=ts, value=spread_bps, metadata={"spread": spread}),
                SignalEvent(source=source, signal_type="depth_imbalance", symbol=symbol, timestamp=ts, value=imbalance),
            ]
        )
    return events


def liquidation_to_signal_events(payload: list[dict[str, Any]], *, source: str = "liquidations", historical_integrity: bool = False) -> list[SignalEvent]:
    events: list[SignalEvent] = []
    for row in payload:
        long_notional = float(row.get("long_liquidation_notional", 0.0))
        short_notional = float(row.get("short_liquidation_notional", 0.0))
        denom = long_notional + short_notional
        imbalance = (long_notional - short_notional) / denom if denom else 0.0
        events.append(
            SignalEvent(
                source=source,
                signal_type="liquidation_imbalance",
                symbol=normalize_symbol(str(row["symbol"])),
                timestamp=normalize_timestamp(row["timestamp"]),
                value=imbalance,
                metadata={
                    "long_liquidation_notional": long_notional,
                    "short_liquidation_notional": short_notional,
                },
                historical_integrity=historical_integrity,
            )
        )
    return events


__all__ = [
    "basis_to_signal_events",
    "funding_to_signal_events",
    "liquidation_to_signal_events",
    "normalize_symbol",
    "normalize_timestamp",
    "open_interest_to_signal_events",
    "orderbook_to_signal_events",
]
