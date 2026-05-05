"""Deterministic artifacts and reporting for Phase 17 Acceptance Harness."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from quant_stack.artifacts.store import save_artifact
from quant_stack.research.experiment_queue import OptimizationRequestRecord


class AcceptanceArtifactSet(BaseModel):
    run_id: str
    timestamp: datetime | None = None
    output_dir: str
    
    query_echo: Dict[str, Any]
    ohlcv_snapshot_meta: Dict[str, Any]
    intelligence_event_count: int
    joined_context_rows: int
    
    baseline_summary: Dict[str, Any]
    candidate_summary: Dict[str, Any]
    
    validation_passed: bool
    validation_critique: str
    
    optimization_proposed: bool = False
    optimization_request_path: Optional[str] = None


def render_acceptance_report(artifact_set: AcceptanceArtifactSet) -> str:
    status = "PASSED" if artifact_set.validation_passed else "FAILED"
    lines = [
        f"# Phase 17 Acceptance Report: {artifact_set.run_id}",
        "",
        f"**Status:** {status}",
        "",
        "## Data Snapshot",
        f"- **Intelligence Events:** {artifact_set.intelligence_event_count}",
        f"- **Joined Context Rows:** {artifact_set.joined_context_rows}",
        "",
        "## Performance Comparison",
        "### Baseline",
        f"```json\n{_json_block(artifact_set.baseline_summary)}\n```",
        "",
        "### Candidate",
        f"```json\n{_json_block(artifact_set.candidate_summary)}\n```",
        "",
        "## Validation Critique",
        artifact_set.validation_critique,
        "",
    ]
    if artifact_set.timestamp is not None:
        lines.insert(2, f"**Timestamp:** {artifact_set.timestamp.isoformat()}")
    if artifact_set.optimization_proposed:
        lines.append("## Optimization Proposed")
        lines.append(f"Proposed optimization record saved to: `{artifact_set.optimization_request_path}`")
        lines.append("")
        
    return "\n".join(lines)


class QueryArtifact(BaseModel):
    query: Dict[str, Any]


class Phase17ReportHelper:
    """Helper to write deterministic Phase 17 artifacts."""
    
    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def save_query_echo(self, query: Dict[str, Any]) -> Path:
        path = self.output_dir / "query_echo.json"
        save_artifact(QueryArtifact(query=query), path)
        return path

    def save_optimization_request(self, request: OptimizationRequestRecord) -> Path:
        path = self.output_dir / "proposed_optimization.json"
        save_artifact(request, path)
        return path

    def save_artifact_set(self, artifact_set: AcceptanceArtifactSet) -> Path:
        path = self.output_dir / "acceptance_manifest.json"
        save_artifact(artifact_set, path)
        return path

    def write_markdown_report(self, artifact_set: AcceptanceArtifactSet) -> Path:
        report_content = render_acceptance_report(artifact_set)
        path = self.output_dir / "acceptance_report.md"
        path.write_text(report_content, encoding="utf-8")
        return path


def _json_block(payload: Dict[str, Any] | List[Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)
