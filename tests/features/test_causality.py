from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl

from quant_stack.features.pipeline import build_feature_dataset
from quant_stack.features.schemas import FeaturePipelineConfig


def _fixture() -> pl.DataFrame:
    n = 300
    ts = [datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n)]
    base = pl.DataFrame(
        {
            "timestamp": ts,
            "available_at": [t + timedelta(minutes=1) for t in ts],
            "symbol": ["BTCUSDT"] * n,
            "timeframe": ["1m"] * n,
            "open": [100.0 + i * 0.1 for i in range(n)],
            "high": [100.2 + i * 0.1 for i in range(n)],
            "low": [99.8 + i * 0.1 for i in range(n)],
            "close": [100.0 + i * 0.1 + ((-1) ** i) * 0.02 for i in range(n)],
            "volume": [10.0 + (i % 7) for i in range(n)],
            "turnover": [1000.0 + i for i in range(n)],
            "funding_rate": [0.0001 if i % 20 == 0 else 0.0 for i in range(n)],
            "funding_available_at": [t + timedelta(minutes=1) for t in ts],
            "open_interest": [1000.0 + i for i in range(n)],
            "oi_available_at": [t + timedelta(minutes=1) for t in ts],
            "basis": [0.001 if i % 15 == 0 else 0.0 for i in range(n)],
            "basis_available_at": [t + timedelta(minutes=1) for t in ts],
        }
    )
    return base


def compute_features_original(df: pl.DataFrame) -> pl.DataFrame:
    return build_feature_dataset(df, config=FeaturePipelineConfig())


def mutate_future_rows(df: pl.DataFrame, cutoff_idx: int, columns: list[str]) -> pl.DataFrame:
    out = df
    for col in columns:
        out = out.with_columns(
            pl.when(pl.arange(0, pl.len()) >= cutoff_idx)
            .then(pl.col(col) * 10)
            .otherwise(pl.col(col))
            .alias(col)
        )
    return out


def test_causal_mutation_preserves_pre_cutoff_features() -> None:
    base = _fixture()
    cutoff = 220
    original = compute_features_original(base)
    mutated = mutate_future_rows(base, cutoff, ["close", "high", "low", "volume", "funding_rate", "open_interest", "basis"])
    recomputed = compute_features_original(mutated)

    feature_cols = [
        "ret_1",
        "realized_vol_60",
        "rsi_14",
        "ema_200",
        "bb_pos_20",
        "volume_zscore_20",
        "funding_zscore_30",
        "oi_zscore_60",
        "basis_zscore_60",
        "forced_selling_proxy",
    ]

    for col in feature_cols:
        lhs = original.get_column(col).to_list()[:cutoff]
        rhs = recomputed.get_column(col).to_list()[:cutoff]
        assert lhs == rhs, f"feature changed before cutoff for {col}"
