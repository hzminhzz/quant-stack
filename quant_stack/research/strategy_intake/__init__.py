"""Strategy intake module for Phase 19A - MACD Divergence + Multi-Timeframe TD Strategy."""

from quant_stack.research.strategy_intake.macd_td_v6_schemas import (
    MACDTDExperimentPlan,
    MACDTDLeakageAudit,
    MACDTDParams,
    MACDTDStrategyIdea,
)

__all__ = [
    "MACDTDParams",
    "MACDTDStrategyIdea",
    "MACDTDExperimentPlan",
    "MACDTDLeakageAudit",
]