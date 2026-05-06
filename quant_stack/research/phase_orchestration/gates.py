"""Deterministic gate functions for Phase 19 subphases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GateResult:
    passed: bool
    reason: str
    details: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def check_artifacts_exist(artifact_dir: Path, required: list[str]) -> tuple[bool, list[str]]:
    missing = []
    for art in required:
        if not (artifact_dir / art).exists():
            missing.append(art)
    return len(missing) == 0, missing


def gate_19b(artifact_root: Path) -> GateResult:
    required_artifacts = [
        "prototype_config.json",
        "data_coverage_summary.json",
        "trade_log.json",
        "equity_curve.json",
        "prototype_metrics.json",
        "leakage_fix_verification.json",
        "eligibility_report.json",
    ]

    exists, missing = check_artifacts_exist(artifact_root, required_artifacts)
    if not exists:
        return GateResult(False, f"Missing artifacts: {missing}", {"missing": missing})

    try:
        leak_verif = load_json(artifact_root / "leakage_fix_verification.json")
        if not leak_verif.get("same_bar_execution_removed", False):
            return GateResult(False, "same_bar_execution not removed", leak_verif)

        if not leak_verif.get("nearest_timestamp_replaced", False):
            return GateResult(False, "nearest_timestamp not replaced", leak_verif)

        if not leak_verif.get("extrema_confirmation_delay_enforced", False):
            return GateResult(False, "extrema_confirmation_delay not enforced", leak_verif)

        if leak_verif.get("future_alignment_count", 0) > 0:
            return GateResult(False, "future alignment found", leak_verif)

        if leak_verif.get("pandas_used_in_core_path", True):
            return GateResult(False, "pandas used in core path", leak_verif)

        eligibility = load_json(artifact_root / "eligibility_report.json")
        verdict = eligibility.get("eligibility_decision", "not_eligible")

        if verdict == "not_eligible":
            return GateResult(False, f"Phase 19B not eligible: {eligibility.get('reason', 'unknown')}", eligibility)

        if verdict in ["eligible_for_economic_validation", "eligible_with_remaining_risks"]:
            metrics = load_json(artifact_root / "prototype_metrics.json")
            return GateResult(True, "Phase 19B gate passed", {
                "verdict": verdict,
                "total_trades": metrics.get("total_trades", 0),
                "return_pct": metrics.get("total_return_pct", 0),
            })

        return GateResult(False, f"Unknown eligibility verdict: {verdict}", {"verdict": verdict})

    except FileNotFoundError as e:
        return GateResult(False, f"Artifact not found: {e}", {})
    except json.JSONDecodeError as e:
        return GateResult(False, f"Invalid JSON: {e}", {})


def gate_19c(artifact_root: Path) -> GateResult:
    required_artifacts = [
        "symbol_metrics.json",
        "economic_validation_score.json",
        "eligibility_report.json",
    ]

    exists, missing = check_artifacts_exist(artifact_root, required_artifacts)
    if not exists:
        return GateResult(False, f"Missing artifacts: {missing}", {"missing": missing})

    try:
        score = load_json(artifact_root / "economic_validation_score.json")
        classification = score.get("classification", "weak")

        if classification not in ["promising", "mixed"]:
            return GateResult(False, f"Economic validation failed: {classification}", score)

        metrics = load_json(artifact_root / "symbol_metrics.json")
        symbols = metrics.get("symbols", {})

        has_sufficient_trades = False
        for sym, sym_metrics in symbols.items():
            if sym_metrics.get("trade_count", 0) >= 10:
                has_sufficient_trades = True
                break

        if not has_sufficient_trades:
            return GateResult(False, "No symbol has sufficient trades", metrics)

        return GateResult(True, f"Phase 19C gate passed: {classification}", {
            "classification": classification,
            "symbols": list(symbols.keys()),
        })

    except (FileNotFoundError, json.JSONDecodeError) as e:
        return GateResult(False, f"Error reading artifacts: {e}", {})


def gate_19d(artifact_root: Path) -> GateResult:
    required_artifacts = [
        "robustness_score.json",
        "walk_forward_metrics.json",
        "cost_sensitivity.json",
        "eligibility_report.json",
    ]

    exists, missing = check_artifacts_exist(artifact_root, required_artifacts)
    if not exists:
        return GateResult(False, f"Missing artifacts: {missing}", {"missing": missing})

    try:
        score = load_json(artifact_root / "robustness_score.json")
        classification = score.get("classification", "rejected")

        if classification == "rejected":
            return GateResult(False, f"Robustness rejected: {score.get('reason', 'unknown')}", score)

        cost_sens = load_json(artifact_root / "cost_sensitivity.json")
        catastrophic = cost_sens.get("catastrophic_at_normal_costs", False)
        if catastrophic:
            return GateResult(False, "Cost sensitivity is catastrophic", cost_sens)

        if classification in ["robust", "promising_but_fragile"]:
            return GateResult(True, f"Phase 19D gate passed: {classification}", {
                "classification": classification,
            })

        if classification == "inconclusive":
            report_path = artifact_root / "report.md"
            if report_path.exists():
                with open(report_path) as f:
                    content = f.read()
                    if "more data is the only blocker" in content.lower():
                        return GateResult(True, "Phase 19D inconclusive but data-limited", {})

        return GateResult(False, f"Unknown robustness classification: {classification}", score)

    except (FileNotFoundError, json.JSONDecodeError) as e:
        return GateResult(False, f"Error reading artifacts: {e}", {})


def gate_19e(artifact_root: Path) -> GateResult:
    required_artifacts = [
        "sensitivity_score.json",
        "selected_research_candidate.json",
        "eligibility_report.json",
    ]

    exists, missing = check_artifacts_exist(artifact_root, required_artifacts)
    if not exists:
        return GateResult(False, f"Missing artifacts: {missing}", {"missing": missing})

    try:
        score = load_json(artifact_root / "sensitivity_score.json")
        classification = score.get("classification", "rejected")

        if classification in ["fragile_needs_more_data", "rejected"]:
            return GateResult(False, f"Sensitivity failed: {classification}", score)

        candidate = load_json(artifact_root / "selected_research_candidate.json")

        if classification in ["keep_baseline", "stable_alternative_found"]:
            return GateResult(True, f"Phase 19E gate passed: {classification}", {
                "classification": classification,
                "candidate": candidate.get("name", "unknown"),
            })

        return GateResult(False, f"Unknown sensitivity classification: {classification}", score)

    except (FileNotFoundError, json.JSONDecodeError) as e:
        return GateResult(False, f"Error reading artifacts: {e}", {})


def gate_19f(artifact_root: Path) -> GateResult:
    required_artifacts = [
        "final_research_decision.json",
        "macd_td_candidate_metrics.json",
        "rsi_momentum_candidate_metrics.json",
    ]

    exists, missing = check_artifacts_exist(artifact_root, required_artifacts)
    if not exists:
        return GateResult(False, f"Missing artifacts: {missing}", {"missing": missing})

    try:
        decision = load_json(artifact_root / "final_research_decision.json")
        classification = decision.get("classification", "reject_macd_td")

        return GateResult(True, f"Phase 19F completed: {classification}", {
            "classification": classification,
            "recommendation": decision.get("recommendation", ""),
        })

    except (FileNotFoundError, json.JSONDecodeError) as e:
        return GateResult(False, f"Error reading artifacts: {e}", {})


__all__ = [
    "GateResult",
    "gate_19b",
    "gate_19c",
    "gate_19d",
    "gate_19e",
    "gate_19f",
]