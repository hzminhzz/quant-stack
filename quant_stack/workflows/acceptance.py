"""Canonical wrapper for the Phase 17 acceptance workflow."""

from __future__ import annotations

from pathlib import Path

from quant_stack.research.acceptance_artifacts import AcceptanceArtifactSet
from quant_stack.research.optimization.acceptance_query import AcceptanceQuery, load_acceptance_query
from quant_stack.workflows.acceptance_impl import run_acceptance


def run_acceptance_query(
    query_path: str | Path,
    *,
    output_dir: str | Path,
    fixture_root: str | Path | None = None,
    intelligence_root: str | Path | None = None,
) -> AcceptanceArtifactSet:
    query = load_acceptance_query(query_path)
    output_dir_path = Path(output_dir)
    fixture_root_path = Path(fixture_root) if fixture_root is not None else output_dir_path / "fixtures"
    intelligence_root_path = Path(intelligence_root) if intelligence_root is not None else output_dir_path / "intelligence"
    return run_acceptance(
        query,
        output_dir=output_dir_path,
        fixture_root=fixture_root_path,
        intelligence_root=intelligence_root_path,
    )


__all__ = ["AcceptanceQuery", "load_acceptance_query", "run_acceptance_query"]
