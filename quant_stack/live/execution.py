"""Execution primitives for future broker adapters."""

from __future__ import annotations

from pydantic import BaseModel


class OrderIntent(BaseModel):
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"


__all__ = ["OrderIntent"]
