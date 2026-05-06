from __future__ import annotations

import polars as pl

from quant_stack.features.momentum import add_momentum_features


def test_rsi_length_and_warmup() -> None:
    df = pl.DataFrame({"close": [1.0, 2.0, 3.0, 2.0, 2.0, 3.0, 4.0, 5.0, 4.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]})
    out = add_momentum_features(df, 14)
    assert out.height == df.height
    assert out["rsi_14"].to_list()[0] is None


def test_rsi_zero_loss_safe() -> None:
    df = pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0] * 5})
    out = add_momentum_features(df, 14)
    assert "rsi_14" in out.columns


def test_momentum_slope_no_future_leak() -> None:
    df = pl.DataFrame({"close": list(range(1, 40))})
    out = add_momentum_features(df, 14)
    assert out["momentum_slope_10"].to_list()[0] is None
