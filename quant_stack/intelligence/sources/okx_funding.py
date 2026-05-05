"""Read-only OKX funding source adapter."""

from __future__ import annotations

from typing import Any

from quant_stack.intelligence.normalize import funding_to_signal_events, normalize_symbol
from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.sources.okx_market import fetch_okx_public


def fetch_funding_rates(symbol: str) -> list[dict[str, Any]]:
    inst_id = normalize_symbol(symbol)
    payload = fetch_okx_public("/api/v5/public/funding-rate", {"instId": inst_id})
    data = payload.get("data", [])
    return [
        {
            "symbol": inst_id,
            "timestamp": item.get("fundingTime") or item.get("ts"),
            "funding_rate": item.get("fundingRate"),
            "next_funding_time": item.get("nextFundingTime"),
        }
        for item in data
    ]


def funding_events_from_rows(rows: list[dict[str, Any]]) -> list[SignalEvent]:
    return funding_to_signal_events(rows)


__all__ = ["fetch_funding_rates", "funding_events_from_rows"]
