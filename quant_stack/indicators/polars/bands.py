"""Band indicators implemented as Polars expressions."""

from __future__ import annotations

import polars as pl


def bollinger_bands(
    column: str = "close",
    *,
    window: int = 20,
    num_std: float = 2.0,
    middle_alias: str = "bb_middle",
    upper_alias: str = "bb_upper",
    lower_alias: str = "bb_lower",
) -> list[pl.Expr]:
    """Bollinger middle, upper, and lower band expressions."""

    if window <= 0:
        raise ValueError("window must be positive")
    if num_std <= 0:
        raise ValueError("num_std must be positive")
    middle = pl.col(column).rolling_mean(window_size=window, min_samples=window)
    std = pl.col(column).rolling_std(window_size=window, min_samples=window, ddof=0)
    return [
        middle.alias(middle_alias),
        (middle + (num_std * std)).alias(upper_alias),
        (middle - (num_std * std)).alias(lower_alias),
    ]


__all__ = ["bollinger_bands"]
