"""Typed critic wrapper (explanation-only authority)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from pydantic_ai import Agent

from quant_stack.research.optimization.schemas import BacktestCritique
from quant_stack.research.schemas import BacktestSummary, ValidationReport


CRITIC_SYSTEM_PROMPT = (
    "You are a quantitative backtest critic. Explain weaknesses and next suggestions. "
    "You are NOT the final pass/fail authority; deterministic validation and objective scoring decide approval. "
    "Never suggest broker/live execution commands or production deployment."
)


@dataclass(frozen=True)
class OptimizerCriticAgent:
    model: Any

    def build(self) -> Any:
        return Agent(self.model, output_type=BacktestCritique, system_prompt=CRITIC_SYSTEM_PROMPT)

    async def critique(self, *, summary: BacktestSummary, validation: ValidationReport) -> BacktestCritique:
        prompt = json.dumps({"backtest_summary": summary.model_dump(), "validation_report": validation.model_dump()}, separators=(",", ":"))
        result = await self.build().run(prompt)
        output = getattr(result, "output", getattr(result, "data", result))
        return output if isinstance(output, BacktestCritique) else BacktestCritique.model_validate(output)


__all__ = ["OptimizerCriticAgent"]
