"""Read-only OKX spot/perp basis adapter."""

from __future__ import annotations

from typing import Any

from quant_stack.intelligence.normalize import basis_to_signal_events, normalize_symbol
from quant_stack.intelligence.schemas import SignalEvent
from quant_stack.intelligence.sources.okx_market import fetch_okx_public


def fetch_spot_perp_basis(symbol: str) -> list[dict[str, Any]]:
    base_quote_swap = normalize_symbol(symbol)
    spot = base_quote_swap.replace("-SWAP", "")
    perp_ticker = fetch_okx_public("/api/v5/market/ticker", {"instId": base_quote_swap}).get("data", [])
    spot_ticker = fetch_okx_public("/api/v5/market/ticker", {"instId": spot}).get("data", [])
    if not perp_ticker or not spot_ticker:
        return []
    perp_row = perp_ticker[0]
    spot_row = spot_ticker[0]
    ts = perp_row.get("ts") or spot_row.get("ts")
    return [
        {
            "symbol": base_quote_swap,
            "timestamp": ts,
            "spot_price": spot_row.get("last"),
            "perp_price": perp_row.get("last"),
        }
    ]


def basis_events_from_rows(rows: list[dict[str, Any]]) -> list[SignalEvent]:
    return basis_to_signal_events(rows)


__all__ = ["basis_events_from_rows", "fetch_spot_perp_basis"]
