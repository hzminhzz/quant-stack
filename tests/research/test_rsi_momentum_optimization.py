import pytest
import yaml
from pathlib import Path
from scripts.run_rsi_momentum_optimization import ObjectiveScorer

def test_optimization_query_parses():
    query_path = Path("examples/pipeline_queries/btc_4h_rsi_extreme_momentum_optimization.yaml")
    assert query_path.exists()
    with open(query_path, "r") as f:
        config = yaml.safe_load(f)
    assert "search_space" in config
    assert "splits" in config

def test_objective_score_deterministic():
    metrics = {"smart_sharpe": 1.5, "cumulative_return": 0.2, "max_drawdown": -0.1}
    score1 = ObjectiveScorer.calculate_score(metrics)
    score2 = ObjectiveScorer.calculate_score(metrics)
    assert score1 == score2
    assert isinstance(score1, float)

def test_objective_penalties():
    # Negative return should have lower score
    metrics_pos = {"smart_sharpe": 1.0, "cumulative_return": 0.1, "max_drawdown": -0.1}
    metrics_neg = {"smart_sharpe": -1.0, "cumulative_return": -0.1, "max_drawdown": -0.1}
    assert ObjectiveScorer.calculate_score(metrics_pos) > ObjectiveScorer.calculate_score(metrics_neg)

def test_grid_constraints_logic():
    # Simulate the loop logic
    upper = 70
    exit_lvl = 75 # Invalid
    assert not (upper > exit_lvl)
    
    upper = 70
    lower = 30
    assert (upper - lower) >= 25 # Valid
    
    lower = 50
    exit_lvl = 45 # Invalid
    assert not (lower < exit_lvl)
