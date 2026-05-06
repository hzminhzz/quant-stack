from __future__ import annotations

import polars as pl

from quant_stack.features.forced_flow import add_forced_flow_proxy_features
from quant_stack.features.schemas import FeatureThresholdConfig


def test_forced_flow_and_liquidation_proxies() -> None:
    df = pl.DataFrame(
        {
            "ret_1": [0.0, -0.1, 0.1],
            "volume_zscore_20": [0.0, 3.0, 3.0],
            "oi_flush": [False, True, True],
            "bb_reclaim_lower": [False, True, False],
            "bb_reclaim_upper": [False, False, True],
            "return_zscore_60": [0.0, -3.0, 3.0],
        }
    )
    out = add_forced_flow_proxy_features(df, FeatureThresholdConfig())
    assert out["forced_selling_proxy"].to_list()[1] is True
    assert out["forced_buying_proxy"].to_list()[2] is True
    assert out["liquidation_proxy_long"].to_list()[1] is True
    assert out["liquidation_proxy_short"].to_list()[2] is True
