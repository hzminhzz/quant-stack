"""Tests for MACD-TD V6 strategy intake."""

import json
from pathlib import Path

import pytest

from quant_stack.research.strategy_intake.macd_td_v6_schemas import (
    MACDTDExperimentPlan,
    MACDTDLeakageAudit,
    MACDTDParams,
    MACDTDStrategyIdea,
    MACDTDFeatureAvailability,
    MACDTDExecutionSemanticsAudit,
    MACDTDSourceStrategySummary,
)
from quant_stack.research.strategy_intake.macd_td_v6_intake import (
    create_experiment_plan,
    create_execution_semantics_audit,
    create_feature_availability,
    create_leakage_audit,
    create_source_strategy_summary,
    create_strategy_idea,
    generate_artifacts,
    load_intake_query,
)


class TestMACDTDParams:
    def test_default_params(self):
        params = MACDTDParams()
        assert params.macd_fast_period == 12
        assert params.macd_slow_period == 26
        assert params.macd_signal_period == 9
        assert params.atr_period == 14
        assert params.ema_fast_period == 20
        assert params.ema_slow_period == 60
        assert params.rsi_period == 14

    def test_custom_params(self):
        params = MACDTDParams(
            macd_fast_period=8,
            macd_slow_period=17,
            macd_signal_period=6,
            min_divergence_strength=0.3,
        )
        assert params.macd_fast_period == 8
        assert params.min_divergence_strength == 0.3

    def test_validation_bounds(self):
        with pytest.raises(Exception):
            MACDTDParams(macd_fast_period=0)
        with pytest.raises(Exception):
            MACDTDParams(min_divergence_strength=1.5)


class TestMACDTDStrategyIdea:
    def test_create_strategy_idea(self):
        idea = create_strategy_idea()
        assert idea.name == "macd_td_v6"
        assert "MACD divergence" in idea.hypothesis
        assert "15m" in idea.timeframes
        assert "macd_12_26_9" in idea.required_features


class TestMACDTDExperimentPlan:
    def test_create_experiment_plan(self):
        query = {
            "symbols": ["BTC-USDT", "ETH-USDT"],
            "params": {"fee_bps": 5, "slippage_bps": 2},
            "data": {"source_timeframe": "1m"},
            "artifacts": {"output_dir": "artifacts/test"},
        }
        plan = create_experiment_plan(query)
        assert "BTC-USDT" in plan.symbols
        assert plan.fee_bps == 5
        assert plan.source_timeframe == "1m"


class TestMACDTDLeakageAudit:
    def test_create_leakage_audit(self):
        audit = create_leakage_audit()
        assert audit.same_bar_execution_risk is True
        assert audit.nearest_timestamp_leakage_risk is True
        assert audit.verdict in ["eligible", "eligible_with_risks", "not_eligible"]


class TestMACDTDSourceStrategySummary:
    def test_create_source_summary(self):
        summary = create_source_strategy_summary()
        assert "MACD (12,26,9)" in summary.indicators
        assert "ATR (14)" in summary.indicators
        assert "TD9 setup signals" in summary.indicators
        assert len(summary.entry_rules) > 0
        assert len(summary.exit_rules) > 0


class TestMACDTDFeatureAvailability:
    def test_create_feature_availability(self):
        features = create_feature_availability()
        assert features.macd == "available"
        assert features.atr == "available"
        assert features.rsi == "available"
        assert features.td_setup == "missing"
        assert features.divergence_detection == "missing"


class TestMACDTDExecutionSemanticsAudit:
    def test_create_execution_semantics(self):
        semantics = create_execution_semantics_audit()
        assert semantics.primary_event_clock == "15m completed bars"
        assert semantics.lower_timeframe_alignment == "asof_backward"
        assert semantics.entry_execution == "next_15m_open"


class TestLoadIntakeQuery:
    def test_load_yaml(self, tmp_path):
        yaml_content = """
query_id: test_intake
symbols:
  - BTC-USDT
params:
  fee_bps: 5
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        result = load_intake_query(yaml_file)
        assert result["query_id"] == "test_intake"
        assert result["symbols"] == ["BTC-USDT"]


class TestGenerateArtifacts:
    def test_generate_all_artifacts(self, tmp_path):
        yaml_content = """
query_id: test
symbols:
  - BTC-USDT
params:
  fee_bps: 5
data:
  mode: local_or_synthetic
artifacts:
  output_dir: {}
""".format(tmp_path / "artifacts")

        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        artifacts = generate_artifacts(yaml_file, tmp_path / "artifacts")

        for name, path in artifacts.items():
            assert path.exists(), f"Artifact {name} not found at {path}"
            with open(path) as f:
                data = json.load(f)
                assert data is not None


class TestNoLiveBinanceDependency:
    def test_no_binance_import(self):
        import quant_stack.research.strategy_intake.macd_td_v6_intake as intake_module

        source = intake_module.__file__
        with open(source) as f:
            content = f.read()
            assert "binance" not in content.lower()
            assert "get_klines" not in content

    def test_no_broker_import(self):
        import quant_stack.research.strategy_intake.macd_td_v6_intake as intake_module

        source = intake_module.__file__
        with open(source) as f:
            content = f.read()
            assert "broker" not in content.lower()
            assert "order" not in content.lower() or "timeframe" in content.lower()


class TestNoPandasInCore:
    def test_schemas_no_pandas(self):
        import quant_stack.research.strategy_intake.macd_td_v6_schemas as schemas_module

        source = schemas_module.__file__
        with open(source) as f:
            content = f.read()
            assert "import pandas" not in content
            assert "from pandas" not in content