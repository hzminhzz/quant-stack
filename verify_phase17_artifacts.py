import json
from datetime import datetime, timezone
from pathlib import Path
from quant_stack.research.acceptance_artifacts import AcceptanceArtifactSet, Phase17ReportHelper
from quant_stack.research.optimization.schemas import OptimizationRequest, AcceptanceCriteria
from quant_stack.research.experiment_queue import OptimizationRequestRecord

def verify_artifacts():
    output_dir = Path("artifacts/test_acceptance_run")
    helper = Phase17ReportHelper(output_dir)
    
    # Mock data
    artifact_set = AcceptanceArtifactSet(
        run_id="test-run-123",
        output_dir=".",
        query_echo={"symbol": "BTC/USDT", "timeframe": "1h"},
        ohlcv_snapshot_meta={"rows": 1000},
        intelligence_event_count=50,
        joined_context_rows=950,
        baseline_summary={"sharpe": 1.2, "return": 0.15},
        candidate_summary={"sharpe": 1.5, "return": 0.18},
        validation_passed=True,
        validation_critique="Candidate shows improved risk-adjusted returns with stable context gating.",
        optimization_proposed=True,
        optimization_request_path="proposed_optimization.json"
    )
    
    # Mock optimization request
    opt_req = OptimizationRequest(
        strategy_name="rsi_sma",
        symbols=["BTC/USDT"],
        timeframes=["1h"],
        train_period="2023-01-01 to 2023-06-30",
        test_period="2023-07-01 to 2023-12-31",
        acceptance_criteria=AcceptanceCriteria()
    )
    
    # Write artifacts
    helper.save_query_echo(artifact_set.query_echo)
    helper.save_optimization_request(
        OptimizationRequestRecord(
            request_id="phase17-test-run-proposed",
            request_payload=opt_req.model_dump(),
            created_by="workflow",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    )
    helper.save_artifact_set(artifact_set)
    helper.write_markdown_report(artifact_set)
    
    # Verify existence
    expected_files = [
        "query_echo.json",
        "proposed_optimization.json",
        "acceptance_manifest.json",
        "acceptance_report.md"
    ]
    
    for f in expected_files:
        p = output_dir / f
        if not p.exists():
            raise FileNotFoundError(f"Missing expected artifact: {p}")
        print(f"Verified: {p}")
        
    # Verify deterministic JSON content (partial)
    manifest = json.loads((output_dir / "acceptance_manifest.json").read_text())
    assert manifest["run_id"] == "test-run-123"
    assert manifest["validation_passed"] is True
    assert manifest["output_dir"] == "."
    
    report = (output_dir / "acceptance_report.md").read_text()
    assert "# Phase 17 Acceptance Report: test-run-123" in report
    assert "## Data Snapshot" in report
    
    print("All artifacts verified successfully.")

if __name__ == "__main__":
    verify_artifacts()
