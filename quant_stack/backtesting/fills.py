"""Fill policy contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FillPolicy(BaseModel):
    """Simple market fill policy for bar-based signal backtests."""

    price: Literal["close_to_close"] = "close_to_close"
    signal_lag_bars: int = 1


__all__ = ["FillPolicy"]
