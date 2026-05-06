from __future__ import annotations

import polars as pl

from quant_stack.features.returns import add_return_features
from quant_stack.features.volatility import add_volatility_features


def test_range_true_range_and_atr() -> None:
    df = pl.DataFrame(
        {
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.0, 11.0, 12.0],
        }
    )
    out = add_return_features(df, [1, 5, 15, 60])
    out = add_volatility_features(out, [20, 60, 240], 14)
    assert "range_pct" in out.columns
    assert "true_range" in out.columns
    assert "atr_14" in out.columns


def test_atr_warmup_nulls() -> None:
    df = pl.DataFrame({"high": [2.0] * 20, "low": [1.0] * 20, "close": [1.5] * 20})
    out = add_return_features(df, [1, 5, 15, 60])
    out = add_volatility_features(out, [20, 60, 240], 14)
    assert out["atr_14"].to_list()[0] is None
