from typing import Any
from pydantic import BaseModel, Field
import polars as pl
import numpy as np
from .base import StrategyFamily
from engine.grid_backtester import simulate_dynamic_grid, calculate_grid_metrics

class GridParams(BaseModel):
    num_levels: int = Field(20, ge=2)
    grid_width_pct: float = Field(0.10, gt=0)
    fee_pct: float = Field(0.0002, ge=0)

class GridFamily(StrategyFamily):
    @property
    def name(self) -> str:
        return "volatility_grid"

    def build_initial_prompt(self, seed_info: str) -> str:
        return f"Propose a Dynamic Boundary Chase grid strategy based on: {seed_info}"

    def build_retry_prompt(self, critique: str) -> str:
        return f"Refine the grid strategy based on this critique: {critique}"

    def build_seed_hint(self, signal_data: dict[str, Any]) -> str:
        return f"""
        Strategy: Dynamic Boundary Grid (Chase)
        Levels (G): {signal_data.get('num_levels', 20)}
        Width (W): {signal_data.get('grid_width_pct', 0.10) * 100}%
        Fees: {signal_data.get('fee_pct', 0.0002) * 100}% (Maker)
        Logic: Re-center grid whenever price breaches boundaries.
        """

    def signal_model(self) -> type[BaseModel]:
        return GridParams

    def build_discovery_prompt(self, raw_markdown: str, paper_context: str) -> str:
        return f"Extract grid parameters from this text: {raw_markdown}\nContext: {paper_context}"

    def build_paper_query(self, signal_data: dict[str, Any]) -> str:
        return "dynamic grid trading boundary chase volatility harvesting"

    def validate_params(self, params: dict[str, Any]) -> GridParams:
        return GridParams(**params)

    def prepare_market_data(self, raw_df: pl.DataFrame) -> pl.DataFrame:
        return raw_df.sort("timestamp")

    def simulate(self, close_prices: np.ndarray, params: GridParams):
        return simulate_dynamic_grid(
            close_prices=close_prices,
            num_levels=params.num_levels,
            grid_width_pct=params.grid_width_pct,
            fee_pct=params.fee_pct
        )

    def format_params(self, params: GridParams) -> str:
        return f"G={params.num_levels}, W={params.grid_width_pct*100}%"

    def build_execution_prompt(self, params: GridParams, class_name: str) -> str:
        return f"Implement a grid strategy with {self.format_params(params)} in class {class_name}"

    def validate_backtest_results(self, metrics: dict[str, Any]) -> bool:
        return metrics.get("Max Drawdown", 0) > -0.15 and metrics.get("Total Return", 0) > 0
