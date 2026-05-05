"""Strict acceptance-query contract for Phase 17 pipeline harnesses."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContextGate(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    join_key: Literal["timestamp"] = "timestamp"
    frame_kind: Literal["timestamped_bar"] = "timestamped_bar"
    required_context_tags: list[str] = Field(default_factory=list)
    max_spread_bps: float = Field(..., ge=0.0)
    min_depth_imbalance: float = Field(default=-1.0, ge=-1.0, le=1.0)
    max_depth_imbalance: float = Field(default=1.0, ge=-1.0, le=1.0)
    candidate_scope: Literal["post_strategy_pre_backtest_context_gating"] = "post_strategy_pre_backtest_context_gating"

    @model_validator(mode="after")
    def _check_depth_window(self) -> "ContextGate":
        if self.min_depth_imbalance > self.max_depth_imbalance:
            raise ValueError("min_depth_imbalance must be <= max_depth_imbalance")
        return self


class AcceptanceQuery(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    strategy_name: Literal["rsi_sma", "bb_breakout"]
    symbol: Literal["BTC"]
    timeframe: Literal["1m", "1h"]
    context_gate: ContextGate
    artifact_mode: Literal["proposed_only"] = "proposed_only"

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, symbol: str) -> str:
        return symbol.strip().upper()

    @field_validator("timeframe")
    @classmethod
    def _normalize_timeframe(cls, timeframe: str) -> str:
        return timeframe.strip().lower()

    @model_validator(mode="after")
    def _check_strategy_timeframe(self) -> "AcceptanceQuery":
        expected_timeframe = {"rsi_sma": "1m", "bb_breakout": "1h"}[self.strategy_name]
        if self.timeframe != expected_timeframe:
            raise ValueError(f"{self.strategy_name} requires timeframe {expected_timeframe}")
        return self


def load_acceptance_query(path: str | Path) -> AcceptanceQuery:
    raw = cast(object, yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    if raw is None:
        raise ValueError(f"empty acceptance query: {path}")
    if not isinstance(raw, dict):
        raise ValueError(f"acceptance query must be a mapping: {path}")
    payload: dict[str, object] = cast(dict[str, object], raw)
    return AcceptanceQuery.model_validate(payload)


__all__ = ["AcceptanceQuery", "ContextGate", "load_acceptance_query"]
