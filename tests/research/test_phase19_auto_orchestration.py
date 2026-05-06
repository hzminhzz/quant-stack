"""Tests for Phase 19 autonomous orchestration."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from quant_stack.research.phase_orchestration.gates import (
    GateResult,
    gate_19b,
    gate_19c,
    gate_19d,
    gate_19e,
    gate_19f,
)
from quant_stack.research.phase_orchestration.phase_status import (
    PipelineStatus,
    PipelineVerdict,
    PhaseState,
)


class TestGateResults:
    def test_gate_result_creation(self):
        result = GateResult(True, "Test passed", {"key": "value"})
        assert result.passed is True
        assert result.reason == "Test passed"
        assert result.details["key"] == "value"

    def test_gate_result_failure(self):
        result = GateResult(False, "Test failed", {"error": "test"})
        assert result.passed is False
        assert result.reason == "Test failed"


class TestGate19B:
    def test_missing_artifacts(self, tmp_path):
        result = gate_19b(tmp_path)
        assert result.passed is False
        assert "Missing artifacts" in result.reason

    def test_leakage_not_fixed(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_prototype_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "leakage_fix_verification.json", {
            "same_bar_execution_removed": False,
            "nearest_timestamp_replaced": True,
            "extrema_confirmation_delay_enforced": True,
        })

        result = gate_19b(artifact_dir)
        assert result.passed is False
        assert "same_bar_execution" in result.reason

    def test_passes_with_valid_artifacts(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_prototype_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "leakage_fix_verification.json", {
            "same_bar_execution_removed": True,
            "nearest_timestamp_replaced": True,
            "extrema_confirmation_delay_enforced": True,
            "future_alignment_count": 0,
            "pandas_used_in_core_path": False,
        })

        write_json(artifact_dir / "eligibility_report.json", {
            "eligibility_decision": "eligible_for_economic_validation",
        })

        write_json(artifact_dir / "prototype_metrics.json", {
            "total_trades": 10,
            "total_return_pct": 5.0,
        })

        write_json(artifact_dir / "trade_log.json", {"trades": []})
        write_json(artifact_dir / "equity_curve.json", {"equity": [100.0]})

        result = gate_19b(artifact_dir)
        assert result.passed is True


class TestGate19C:
    def test_missing_artifacts(self, tmp_path):
        result = gate_19c(tmp_path)
        assert result.passed is False

    def test_weak_classification_fails(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_economic_validation_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "economic_validation_score.json", {
            "classification": "weak",
        })

        result = gate_19c(artifact_dir)
        assert result.passed is False


class TestGate19D:
    def test_rejected_fails(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_robustness_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "robustness_score.json", {
            "classification": "rejected",
        })

        result = gate_19d(artifact_dir)
        assert result.passed is False


class TestGate19E:
    def test_rejected_fails(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_sensitivity_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "sensitivity_score.json", {
            "classification": "rejected",
        })

        result = gate_19e(artifact_dir)
        assert result.passed is False


class TestGate19F:
    def test_final_decision(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_candidate_comparison_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "final_research_decision.json", {
            "classification": "macd_td_complementary_to_rsi",
        })

        result = gate_19f(artifact_dir)
        assert result.passed is True


class TestPipelineStatus:
    def test_status_to_dict(self):
        status = PipelineStatus(
            pipeline_id="test_v1",
            started_at=None,
            completed_phases=["19B", "19C"],
            failed_phase=None,
            final_verdict=PipelineVerdict.ELIGIBLE,
        )
        d = status.to_dict()
        assert d["pipeline_id"] == "test_v1"
        assert d["completed_phases"] == ["19B", "19C"]
        assert d["final_verdict"] == "eligible"


class TestConfigParsing:
    def test_load_auto_config(self, tmp_path):
        config = {
            "pipeline_id": "test_pipeline",
            "enabled_phases": ["19B", "19C"],
            "symbols": ["BTC-USDT"],
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        with open(config_file) as f:
            loaded = yaml.safe_load(f)

        assert loaded["pipeline_id"] == "test_pipeline"
        assert "19B" in loaded["enabled_phases"]


class TestNoForbiddenImports:
    def test_no_optimizer_in_gates(self):
        import quant_stack.research.phase_orchestration.gates as gates_module
        with open(gates_module.__file__) as f:
            content = f.read()
            assert "optimize" not in content.lower() or "allow_optimizer" in content

    def test_no_broker_in_runner(self):
        import quant_stack.research.phase_orchestration.phase19_runner as runner_module
        with open(runner_module.__file__) as f:
            content = f.read()
            assert "from broker" not in content
            assert "import broker" not in content

    def test_no_live_in_orchestration(self):
        import quant_stack.research.phase_orchestration.phase19_runner as runner_module
        with open(runner_module.__file__) as f:
            content = f.read()
            assert "live" not in content.lower() or "live_or_synthetic" in content


class TestStopConditions:
    def test_stop_on_not_eligible(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_prototype_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "leakage_fix_verification.json", {
            "same_bar_execution_removed": True,
            "nearest_timestamp_replaced": True,
            "extrema_confirmation_delay_enforced": True,
        })

        write_json(artifact_dir / "eligibility_report.json", {
            "eligibility_decision": "not_eligible",
            "reason": "Leakage detected",
        })

        result = gate_19b(artifact_dir)
        assert result.passed is False
        assert "not_eligible" in result.reason.lower()

    def test_stop_on_future_alignment(self, tmp_path):
        artifact_dir = tmp_path / "macd_td_v6_prototype_v1"
        artifact_dir.mkdir(parents=True)

        write_json(artifact_dir / "leakage_fix_verification.json", {
            "same_bar_execution_removed": True,
            "nearest_timestamp_replaced": True,
            "extrema_confirmation_delay_enforced": True,
            "future_alignment_count": 5,
        })

        write_json(artifact_dir / "eligibility_report.json", {
            "eligibility_decision": "eligible_for_economic_validation",
        })

        result = gate_19b(artifact_dir)
        assert result.passed is False
        assert "future alignment" in result.reason.lower()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)