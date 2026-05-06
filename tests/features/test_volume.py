from __future__ import annotations

import polars as pl

from quant_stack.features.volume import add_volume_features


def test_volume_zscores_and_spike() -> None:
    df = pl.DataFrame({"volume": [1.0] * 100 + [100.0], "turnover": [10.0] * 101})
    out = add_volume_features(df)
    assert "volume_zscore_20" in out.columns
    assert "volume_zscore_60" in out.columns
    assert "turnover_zscore_20" in out.columns
    assert out["volume_spike_20"].to_list()[-1] is True
