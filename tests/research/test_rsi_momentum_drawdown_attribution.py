import pytest
import polars as pl
from datetime import datetime
from scripts.run_rsi_momentum_drawdown_attribution import calculate_metrics

def test_calculate_metrics_edge_cases():
    # Empty df
    assert calculate_metrics(pl.DataFrame(), "ret") == {}
    
    # All zeros
    df_zeros = pl.DataFrame({"ret": [0.0] * 10})
    res = calculate_metrics(df_zeros, "ret")
    assert res["cumulative_return"] == 0.0
    assert res["smart_sharpe"] == 0.0
    assert res["max_drawdown"] == 0.0

def test_period_splitting_logic():
    dd_start = datetime(2025, 10, 1)
    df = pl.DataFrame({
        "timestamp": [datetime(2025, 9, 30), datetime(2025, 10, 1), datetime(2025, 10, 2)],
        "net_return": [0.01, -0.02, -0.03]
    })
    pre = df.filter(pl.col("timestamp") < dd_start)
    post = df.filter(pl.col("timestamp") >= dd_start)
    assert len(pre) == 1
    assert len(post) == 2

def test_diagnostic_query_parses():
    from pathlib import Path
    import yaml
    query_path = Path("examples/pipeline_queries/rsi_momentum_post_2025_10_drawdown_attribution.yaml")
    assert query_path.exists()
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    assert "diagnostic" in config
    assert config["diagnostic"]["drawdown_start"] == "2025-10-01T00:00:00Z"
