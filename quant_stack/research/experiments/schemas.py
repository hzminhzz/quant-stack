"""Schemas for Phase 18F strategy experiment harness."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ExperimentConfig(BaseModel):
    strategy_name: str = Field(..., min_length=1)
    dataset_path: str
    symbol: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    start: datetime
    end: datetime
    train_start: datetime | None = None
    train_end: datetime | None = None
    test_start: datetime | None = None
    test_end: datetime | None = None
    baseline_params: dict[str, Any] = Field(default_factory=dict)
    context_params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 1.0
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    output_dir: str = "artifacts/research/experiments"
    walk_forward_enabled: bool = False
    walk_forward_train_bars: int | None = None
    walk_forward_test_bars: int | None = None
    walk_forward_step_bars: int | None = None

    @field_validator("strategy_name", "symbol", "timeframe")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("dataset_path", "output_dir")
    @classmethod
    def normalize_paths(cls, value: str) -> str:
        return Path(value).as_posix()

    @model_validator(mode="after")
    def check_dates(self) -> "ExperimentConfig":
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be > 0")
        if self.fee_bps < 0:
            raise ValueError("fee_bps must be >= 0")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")
        if self.train_start is not None and self.train_end is not None and self.train_start >= self.train_end:
            raise ValueError("train_start must be earlier than train_end")
        if self.test_start is not None and self.test_end is not None and self.test_start >= self.test_end:
            raise ValueError("test_start must be earlier than test_end")

        split_values = [self.train_start, self.train_end, self.test_start, self.test_end]
        has_any_split = any(value is not None for value in split_values)
        has_all_split = all(value is not None for value in split_values)
        if has_any_split and not has_all_split:
            raise ValueError("train/test split requires all fields: train_start, train_end, test_start, test_end")

        if has_all_split:
            train_start = self.train_start
            train_end = self.train_end
            test_start = self.test_start
            test_end = self.test_end
            assert train_start is not None and train_end is not None and test_start is not None and test_end is not None

            if not (self.start <= train_start <= self.end and self.start <= train_end <= self.end):
                raise ValueError("train split boundaries must be inside [start, end]")
            if not (self.start <= test_start <= self.end and self.start <= test_end <= self.end):
                raise ValueError("test split boundaries must be inside [start, end]")
            if train_end > test_start:
                raise ValueError("train_end must be <= test_start to avoid overlap")

        if self.walk_forward_enabled:
            if has_any_split:
                raise ValueError("explicit train/test split cannot be combined with walk_forward_enabled=True")
            if self.walk_forward_train_bars is None or self.walk_forward_test_bars is None:
                raise ValueError("walk_forward_train_bars and walk_forward_test_bars are required when walk_forward_enabled=True")
            if self.walk_forward_train_bars <= 0 or self.walk_forward_test_bars <= 0:
                raise ValueError("walk-forward train/test bars must be > 0")
            if self.walk_forward_step_bars is not None and self.walk_forward_step_bars <= 0:
                raise ValueError("walk_forward_step_bars must be > 0 when provided")
        return self


class StrategyExperimentResult(BaseModel):
    strategy_name: str
    mode: Literal["baseline", "context"]
    params: dict[str, Any] = Field(default_factory=dict)
    backtest_result: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class StrategyComparisonReport(BaseModel):
    strategy_name: str
    baseline_result: StrategyExperimentResult
    context_result: StrategyExperimentResult
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    verdict: str
    warnings: list[str] = Field(default_factory=list)


__all__ = ["ExperimentConfig", "StrategyComparisonReport", "StrategyExperimentResult"]
