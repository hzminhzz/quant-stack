from __future__ import annotations

import polars as pl
import pytest

from quant_stack.features.derivatives import add_derivatives_features, add_funding_features
from quant_stack.features.schemas import FeatureThresholdConfig, FeatureWindowConfig


def _frame() -> pl.DataFrame:
    n = 200
    return pl.DataFrame(
        {
            "funding_rate": [0.0] * (n - 1) + [1.0],
            "open_interest": [100.0 + i for i in range(n)],
            "basis": [0.0] * (n - 1) + [0.02],
        }
    )


def test_derivatives_features_created() -> None:
    out = add_derivatives_features(_frame(), FeatureWindowConfig(), FeatureThresholdConfig(), allow_missing=True)
    for col in ["funding_zscore_30", "funding_percentile_90", "oi_change_1", "oi_change_5", "oi_change_pct_5", "oi_zscore_60", "basis_zscore_60", "basis_percentile_90"]:
        assert col in out.columns


def test_missing_funding_handling() -> None:
    df = pl.DataFrame({"open_interest": [1.0, 2.0], "basis": [0.0, 0.1]})
    add_funding_features(df, 30, 2.0, allow_missing=True)
    with pytest.raises(ValueError):
        add_funding_features(df, 30, 2.0, allow_missing=False)
