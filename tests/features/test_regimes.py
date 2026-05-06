from __future__ import annotations

import polars as pl

from quant_stack.features.regimes import add_regime_features
from quant_stack.features.schemas import FeatureThresholdConfig, FeatureWindowConfig


def test_regime_labels() -> None:
    df = pl.DataFrame(
        {
            "trend_strength_50_200": [0.1, -0.1, 0.0],
            "realized_vol_60": [1.0, 2.0, 1.5],
            "funding_positive_extreme": [True, False, False],
            "funding_negative_extreme": [False, True, False],
            "oi_expansion": [True, False, False],
            "oi_flush": [False, True, False],
            "perp_premium_extreme": [True, False, False],
            "perp_discount_extreme": [False, True, False],
        }
    )
    out = add_regime_features(df, FeatureWindowConfig(), FeatureThresholdConfig(), allow_missing=False)
    assert "trend_regime" in out.columns
    assert "funding_regime" in out.columns
    assert "oi_regime" in out.columns
    assert "basis_regime" in out.columns
