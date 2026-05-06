from __future__ import annotations

import polars as pl

from quant_stack.features.bands import add_bollinger_features


def test_bollinger_columns_created() -> None:
    df = pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0] * 20})
    out = add_bollinger_features(df, 20, 2.0)
    for col in [
        "bb_mid_20",
        "bb_upper_20",
        "bb_lower_20",
        "bb_width_20",
        "bb_pos_20",
        "bb_reclaim_lower",
        "bb_reclaim_upper",
        "bb_reclaim_lower_strict",
        "bb_reclaim_upper_strict",
    ]:
        assert col in out.columns


def test_bb_reclaim_logic_past_to_current() -> None:
    df = pl.DataFrame({"close": [10.0] * 19 + [1.0, 10.0, 10.0, 10.0]})
    out = add_bollinger_features(df, 20, 2.0)
    assert any(v is True for v in out["bb_reclaim_lower"].to_list() if v is not None)


def test_bb_reclaim_lower_upper_strict_features() -> None:
    df = pl.DataFrame({"close": [10.0] * 19 + [1.0, 10.0, 20.0, 10.0]})
    out = add_bollinger_features(df, 20, 2.0)
    assert "bb_reclaim_lower_strict" in out.columns
    assert "bb_reclaim_upper_strict" in out.columns
    assert any(v is True for v in out["bb_reclaim_lower_strict"].to_list() if v is not None)
    assert any(v is True for v in out["bb_reclaim_upper_strict"].to_list() if v is not None)
