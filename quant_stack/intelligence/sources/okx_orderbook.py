"""Read-only OKX orderbook adapter."""

from __future__ import annotations

from typing import Any

from quant_stack.intelligence.normalize import normalize_symbol, orderbook_to_signal_events
from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.sources.okx_market import fetch_okx_public


def fetch_orderbook(symbol: str, *, depth: int = 20) -> list[dict[str, Any]]:
    inst_id = normalize_symbol(symbol)
    payload = fetch_okx_public("/api/v5/market/books", {"instId": inst_id, "sz": depth})
    rows: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        bids = item.get("bids", [])
        asks = item.get("asks", [])
        if not bids or not asks:
            continue
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        bid_depth = float(sum(float(level[1]) for level in bids[:depth]))
        ask_depth = float(sum(float(level[1]) for level in asks[:depth]))
        rows.append(
            {
                "symbol": inst_id,
                "timestamp": item.get("ts"),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bid_depth": bid_depth,
                "ask_depth": ask_depth,
            }
        )
    return rows


def orderbook_events_from_rows(rows: list[dict[str, Any]]) -> list[SignalEvent]:
    return orderbook_to_signal_events(rows)


__all__ = ["fetch_orderbook", "orderbook_events_from_rows"]
