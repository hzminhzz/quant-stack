from __future__ import annotations

import polars as pl

from quant_stack.features.trend import add_trend_features


def test_ema_and_distance_columns_created() -> None:
    df = pl.DataFrame({"close": list(range(1, 300))})
    out = add_trend_features(df, [10, 20, 50, 200])
    for col in ["ema_10", "ema_20", "ema_50", "ema_200", "ema_dist_10", "ema_dist_20", "ema_dist_50", "ema_dist_200"]:
        assert col in out.columns
    assert "trend_strength_50_200" in out.columns
