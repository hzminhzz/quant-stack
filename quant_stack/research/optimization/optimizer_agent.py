"""Typed optimizer proposal agent wrapper."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from pydantic_ai import Agent

from quant_stack.research.optimization.schemas import BacktestCritique, OptimizationRequest, StrategyPatchProposal
from quant_stack.research.schemas import BacktestSummary


OPTIMIZER_SYSTEM_PROMPT = (
    "You are a strategy optimizer. Propose bounded research changes only: params/features/logic suggestions. "
    "Never propose broker orders, live execution commands, risk-limit writes, backtester semantic changes, "
    "or direct production deployment. Output only StrategyPatchProposal."
)


@dataclass(frozen=True)
class StrategyOptimizerAgent:
    model: Any

    def build(self) -> Any:
        return Agent(self.model, output_type=StrategyPatchProposal, system_prompt=OPTIMIZER_SYSTEM_PROMPT)

    async def propose(
        self,
        *,
        request: OptimizationRequest,
        latest_summary: BacktestSummary,
        critique: BacktestCritique,
        prior_params: list[dict[str, object]],
    ) -> StrategyPatchProposal:
        prompt = json.dumps(
            {
                "request": request.model_dump(),
                "latest_summary": latest_summary.model_dump(),
                "critique": critique.model_dump(),
                "prior_params": prior_params,
            },
            separators=(",", ":"),
        )
        result = await self.build().run(prompt)
        output = getattr(result, "output", getattr(result, "data", result))
        return output if isinstance(output, StrategyPatchProposal) else StrategyPatchProposal.model_validate(output)


__all__ = ["StrategyOptimizerAgent"]
