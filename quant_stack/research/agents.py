"""Thin PydanticAI orchestration wrappers for research tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from quant_stack.research.prompts import (
    BACKTEST_CRITIC_SYSTEM_PROMPT,
    EXPERIMENT_PLANNER_SYSTEM_PROMPT,
    REPORT_SYSTEM_PROMPT,
    RESEARCH_IDEA_SYSTEM_PROMPT,
)
from quant_stack.research.schemas import BacktestSummary, ExperimentPlan, ResearchCritique, StrategyIdea, ValidationReport


@dataclass(frozen=True)
class ResearchIdeaAgent:
    model: Any

    def build(self) -> Agent:
        return Agent(self.model, output_type=StrategyIdea, system_prompt=RESEARCH_IDEA_SYSTEM_PROMPT)

    async def run(self, *, paper_text: str, market_observation: str, prior_experiment_summaries: list[str]) -> StrategyIdea:
        result = await self.build().run(
            {
                "paper_text": paper_text,
                "market_observation": market_observation,
                "prior_experiment_summaries": prior_experiment_summaries,
            }
        )
        return _extract_output(result, StrategyIdea)

    @staticmethod
    def validate_output(payload: object) -> StrategyIdea:
        return payload if isinstance(payload, StrategyIdea) else StrategyIdea.model_validate(payload)


@dataclass(frozen=True)
class ExperimentPlannerAgent:
    model: Any

    def build(self) -> Agent:
        return Agent(self.model, output_type=ExperimentPlan, system_prompt=EXPERIMENT_PLANNER_SYSTEM_PROMPT)

    async def run(self, *, idea: StrategyIdea, available_data: dict[str, object], strategy_registry: list[str]) -> ExperimentPlan:
        result = await self.build().run(
            {
                "idea": idea.model_dump(),
                "available_data": available_data,
                "strategy_registry": strategy_registry,
            }
        )
        return _extract_output(result, ExperimentPlan)

    @staticmethod
    def validate_output(payload: object) -> ExperimentPlan:
        return payload if isinstance(payload, ExperimentPlan) else ExperimentPlan.model_validate(payload)


@dataclass(frozen=True)
class BacktestCriticAgent:
    model: Any

    def build(self) -> Agent:
        return Agent(self.model, output_type=ResearchCritique, system_prompt=BACKTEST_CRITIC_SYSTEM_PROMPT)

    async def run(self, *, backtest_summary: BacktestSummary, validation_report: ValidationReport) -> ResearchCritique:
        result = await self.build().run(
            {
                "backtest_summary": backtest_summary.model_dump(),
                "validation_report": validation_report.model_dump(),
            }
        )
        return _extract_output(result, ResearchCritique)

    @staticmethod
    def validate_output(payload: object) -> ResearchCritique:
        return payload if isinstance(payload, ResearchCritique) else ResearchCritique.model_validate(payload)


@dataclass(frozen=True)
class ReportAgent:
    model: Any

    def build(self) -> Agent:
        return Agent(self.model, output_type=str, system_prompt=REPORT_SYSTEM_PROMPT)

    async def run(
        self,
        *,
        idea: StrategyIdea,
        backtest_summary: BacktestSummary,
        validation_report: ValidationReport,
        critique: ResearchCritique,
    ) -> str:
        result = await self.build().run(
            {
                "idea": idea.model_dump(),
                "backtest_summary": backtest_summary.model_dump(),
                "validation_report": validation_report.model_dump(),
                "critique": critique.model_dump(),
            }
        )
        return _extract_output(result, str)

    @staticmethod
    def validate_output(payload: object) -> str:
        return str(payload)


def _extract_output(result: object, model_type: type[Any]) -> Any:
    output = getattr(result, "output", getattr(result, "data", result))
    if model_type is str:
        return str(output)
    return output if isinstance(output, model_type) else model_type.model_validate(output)


__all__ = ["BacktestCriticAgent", "ExperimentPlannerAgent", "ReportAgent", "ResearchIdeaAgent"]
