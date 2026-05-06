from __future__ import annotations

import math

import polars as pl

from quant_stack.features.returns import add_return_features


def test_returns_core_values() -> None:
    df = pl.DataFrame({"close": [100.0, 110.0, 121.0]})
    out = add_return_features(df, [1, 5, 15, 60])
    assert out["ret_1"].to_list()[1] == 0.1
    assert out["log_ret_1"].to_list()[1] == math.log(1.1)
    assert out["abs_ret_1"].to_list()[1] == 0.1


def test_returns_no_future_shift() -> None:
    df = pl.DataFrame({"close": [1.0, 2.0, 4.0]})
    out = add_return_features(df, [1, 5, 15, 60])
    assert out["ret_1"].to_list()[0] is None
