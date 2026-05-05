"""Read-only OKX open interest source adapter."""

from __future__ import annotations

from typing import Any

from quant_stack.intelligence.normalize import normalize_symbol, open_interest_to_signal_events
from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.sources.okx_market import fetch_okx_public


def fetch_open_interest(symbol: str) -> list[dict[str, Any]]:
    inst_id = normalize_symbol(symbol)
    payload = fetch_okx_public("/api/v5/public/open-interest", {"instId": inst_id})
    return [
        {
            "symbol": inst_id,
            "timestamp": item.get("ts"),
            "open_interest": item.get("oi"),
            "open_interest_usd": item.get("oiCcy"),
        }
        for item in payload.get("data", [])
    ]


def open_interest_events_from_rows(rows: list[dict[str, Any]]) -> list[SignalEvent]:
    return open_interest_to_signal_events(rows)


__all__ = ["fetch_open_interest", "open_interest_events_from_rows"]
