"""Return transformations implemented as Polars expressions."""

from __future__ import annotations

import polars as pl


def simple_returns(column: str = "close", *, alias: str = "returns") -> pl.Expr:
    """Simple percentage returns."""

    return pl.col(column).pct_change().alias(alias)


def log_returns(column: str = "close", *, alias: str = "log_returns") -> pl.Expr:
    """Log returns computed from current and previous values."""

    return (pl.col(column) / pl.col(column).shift(1)).log().alias(alias)


__all__ = ["log_returns", "simple_returns"]
