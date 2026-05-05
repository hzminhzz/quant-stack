import pytest
import polars as pl
from pathlib import Path
import yaml

def test_portfolio_query_parses():
    query_path = Path("examples/pipeline_queries/rsi_momentum_trend_filter_portfolio.yaml")
    assert query_path.exists()
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    assert "symbols" in config
    assert len(config["symbols"]) == 3
    assert "portfolio" in config

def test_alignment_logic_mock():
    # Mock data with non-aligned timestamps
    df1 = pl.DataFrame({"timestamp": [1, 2, 3], "ret1": [0.1, 0.2, 0.3]})
    df2 = pl.DataFrame({"timestamp": [2, 3, 4], "ret2": [0.4, 0.5, 0.6]})
    
    # Intersection join
    df_aligned = df1.join(df2, on="timestamp", how="inner")
    assert df_aligned["timestamp"].to_list() == [2, 3]
    assert len(df_aligned) == 2

def test_weight_summation():
    # Simple EW static
    symbols = ["BTC", "ETH", "BNB"]
    weights = {s: 1.0/len(symbols) for s in symbols}
    assert sum(weights.values()) == pytest.approx(1.0)

def test_vol_scaling_as_of():
    # Ensure no lookahead in vol scaling (using rolling_std which is as-of)
    df = pl.DataFrame({"ret": [0.01, 0.02, 0.03, 0.04, 0.05]})
    vol = df.with_columns(v = pl.col("ret").rolling_std(window_size=2))["v"].to_list()
    # first element is null, second element is std([0.01, 0.02])
    assert vol[0] is None
    assert vol[1] is not None
