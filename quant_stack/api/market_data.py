"""Market data contract wrappers for API callers."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from quant_stack.data import validate_ohlcv


@dataclass(frozen=True)
class MarketFrameSchema:
    """Canonical OHLCV schema contract for API requests.

    This class documents the required deterministic columns and optional
    enrichment columns expected at the tool boundary.
    """

    required_columns: tuple[str, ...] = ("timestamp", "open", "high", "low", "close", "volume")
    optional_columns: tuple[str, ...] = ("symbol", "timeframe", "bid", "ask", "exchange")


def validate_market_frame(df: pl.DataFrame) -> pl.DataFrame:
    """Validate API market frame against canonical OHLCV constraints."""

    return validate_ohlcv(df, sort=True)


__all__ = ["MarketFrameSchema", "validate_market_frame"]
