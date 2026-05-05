"""Validation contracts for backtest metrics."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationContract(BaseModel):
    max_drawdown_floor: float = -0.16
    max_daily_drawdown_floor: float = -0.08
    min_cagr: float = 0.0


class ValidationResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)


def validate_metrics(metrics: dict[str, object], contract: ValidationContract | None = None) -> ValidationResult:
    active = contract or ValidationContract()
    reasons: list[str] = []
    if float(metrics.get("max_drawdown", 0.0)) < active.max_drawdown_floor:
        reasons.append("max_drawdown below contract floor")
    if float(metrics.get("max_daily_drawdown", 0.0)) < active.max_daily_drawdown_floor:
        reasons.append("max_daily_drawdown below contract floor")
    if float(metrics.get("cagr", 0.0)) < active.min_cagr:
        reasons.append("cagr below contract minimum")
    return ValidationResult(passed=not reasons, reasons=reasons)


__all__ = ["ValidationContract", "ValidationResult", "validate_metrics"]
