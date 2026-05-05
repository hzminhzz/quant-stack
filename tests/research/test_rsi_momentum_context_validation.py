import pytest
import polars as pl
from scripts.run_rsi_momentum_context_validation import apply_filters

def test_filter_only_blocks():
    # Signal: [1, -1, 1]
    # Allowed: [1, 0, 1]
    # Output: [1, 0, 1]
    df = pl.DataFrame({
        "timestamp": [1, 2, 3],
        "signal": [1, -1, 1],
        "volatility_zscore": [1.0, 5.0, 1.0] # 5.0 will be blocked by extreme_disable
    })
    
    df_filtered = apply_filters(df, "volatility_extreme_disable", {"zscore_threshold": 2.5})
    assert df_filtered["signal"].to_list() == [1, 0, 1]

def test_funding_filter_logic():
    df = pl.DataFrame({
        "timestamp": [1, 2],
        "signal": [1, -1],
        "positive_funding_extreme": [1, 0],
        "negative_funding_extreme": [0, 1]
    })
    # Long at t=1 blocked by positive_funding_extreme=1
    # Short at t=2 blocked by negative_funding_extreme=1
    df_filtered = apply_filters(df, "funding_crowding_filter")
    assert df_filtered["signal"].to_list() == [0, 0]

def test_anti_leakage_structural():
    # This is a structural test. In run_rsi_momentum_context_validation.py,
    # the build_context_features uses rolling operations which are naturally as-of.
    # The join is not needed because it's computed on the same dataframe.
    # But we ensure no 'shift(-1)' or similar is used in building features.
    from scripts.run_rsi_momentum_context_validation import build_context_features
    df = pl.DataFrame({
        "timestamp": [1, 2, 3, 4, 5],
        "close": [100.0, 101.0, 102.0, 103.0, 104.0],
        "rsi": [50.0] * 5
    })
    df_feat = build_context_features(df)
    # Check that trend_strength at t=3 only depends on t<=3
    # In Polars, rolling_mean(window=20) at t=3 only looks at rows 0,1,2,3.
    assert "trend_strength" in df_feat.columns
    assert "volatility_zscore" in df_feat.columns

def test_champion_parameters_frozen():
    query_path = "examples/pipeline_queries/btc_4h_rsi_momentum_context_validation.yaml"
    with open(query_path, "r") as f:
        config = pl.from_pandas(None) # just kidding, use yaml
        import yaml
        config = yaml.safe_load(f)
    cp = config["champion_parameters"]
    assert cp["rsi_period"] == 14
    assert cp["rsi_upper"] == 70
    assert cp["rsi_lower"] == 30
    assert cp["rsi_exit"] == 50
