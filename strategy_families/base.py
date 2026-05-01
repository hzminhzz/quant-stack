from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field
import polars as pl


class StrategyProposal(BaseModel):
    strategy_type: str = Field(..., description="Registered strategy family name")
    params: dict[str, Any] = Field(default_factory=dict, description="Family-specific parameter payload")
    rationale: str = Field(..., description="Reasoning based on market context and CRO feedback.")


class StrategyFamily(ABC):
    name: str
    raw_data_timeframe: str = "1m"
    validation_timeframe: str = "1m"

    @abstractmethod
    def build_initial_prompt(self, seed_info: str) -> str: ...

    @abstractmethod
    def build_retry_prompt(self, critique: str) -> str: ...

    @abstractmethod
    def build_seed_hint(self, signal: dict[str, Any]) -> str: ...

    @abstractmethod
    def signal_model(self) -> type[BaseModel]: ...

    @abstractmethod
    def build_discovery_prompt(self, raw_markdown: str, paper_context: str) -> str: ...

    @abstractmethod
    def build_paper_query(self, signal: dict[str, Any]) -> str: ...

    @abstractmethod
    def validate_params(self, params: dict[str, Any]) -> BaseModel: ...

    @abstractmethod
    def prepare_market_data(self, raw_df: pl.DataFrame) -> pl.DataFrame: ...

    @abstractmethod
    def simulate(self, close_prices, params: BaseModel): ...

    @abstractmethod
    def format_params(self, params: BaseModel) -> str: ...

    @abstractmethod
    def build_execution_prompt(self, params: BaseModel, class_name: str) -> str: ...
