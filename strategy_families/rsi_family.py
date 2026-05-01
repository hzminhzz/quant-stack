from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
import polars as pl

from engine.backtester import get_equity_and_trades_rsi
from strategy_families.base import StrategyFamily


class RSIParams(BaseModel):
    short_sma: int = Field(20)
    long_sma: int = Field(100)
    rsi_period: int = Field(14)
    rsi_threshold: float = Field(35.0)
    rsi_side: Literal["below", "above"] = Field("below")

    @field_validator("short_sma", "long_sma", "rsi_period")
    @classmethod
    def check_positive_windows(cls, value: int) -> int:
        if value <= 1:
            raise ValueError("Strategy periods must be greater than 1.")
        return value

    @field_validator("rsi_threshold")
    @classmethod
    def check_rsi_threshold(cls, value: float) -> float:
        if value <= 5 or value >= 95:
            raise ValueError("RSI threshold must be between 5 and 95.")
        return value

    @model_validator(mode="after")
    def check_window_order(self) -> "RSIParams":
        if self.short_sma >= self.long_sma:
            raise ValueError("short_sma must be less than long_sma.")
        return self


class RSISignal(BaseModel):
    asset: str = Field(..., description="Trading asset, e.g. BTC or ETH")
    params: RSIParams
    hypothesis: str = Field(..., description="Short description of the trading logic")
    stop_loss_pct: float = Field(2.5, description="Suggested stop loss percentage")


class RSIStrategyFamily(StrategyFamily):
    name = "rsi"
    raw_data_timeframe = "1m"
    validation_timeframe = "1m"

    def build_initial_prompt(self, seed_info: str) -> str:
        return (
            "Use `get_market_context` first, then propose an SMA+RSI strategy. "
            "Return strategy_type='rsi' and provide params for short_sma, long_sma, rsi_period, "
            "rsi_threshold, and rsi_side. Design for ROBUSTNESS and target 50+ trades in-sample. "
            + seed_info
        )

    def build_retry_prompt(self, critique: str) -> str:
        return (
            "The CRO rejected your last RSI strategy. Here is the critique:\n"
            + critique
            + "\nPropose a revised RSI strategy. Use get_market_context again if needed."
        )

    def build_seed_hint(self, signal: dict[str, Any]) -> str:
        params = signal.get("params", {})
        return (
            f"The Alpha Researcher discovered a signal from paper '{signal.get('source', '?')}': "
            f"asset='{signal.get('asset', '?')}', hypothesis='{signal.get('hypothesis', '?')}', "
            f"params={params}. Use this as your starting hypothesis and refine from there."
        )

    def signal_model(self) -> type[BaseModel]:
        return RSISignal

    def build_discovery_prompt(self, raw_markdown: str, paper_context: str) -> str:
        return (
            "Extract an RSI strategy signal from the source text. Return asset, params, hypothesis, and stop_loss_pct. "
            "Use params with fields short_sma, long_sma, rsi_period, rsi_threshold, and rsi_side. "
            "Use the source text as primary evidence and use retrieved support only as background.\n\n"
            "<source_text>\n"
            f"{raw_markdown}\n"
            "</source_text>\n\n"
            "<retrieved_support>\n"
            f"{paper_context}\n"
            "</retrieved_support>"
        )

    def build_paper_query(self, signal: dict[str, Any]) -> str:
        params = signal.get("params", {})
        asset = str(signal.get("asset", "asset")).strip()
        hypothesis = str(signal.get("hypothesis", "rsi trading strategy")).strip()
        short_sma = params.get("short_sma", "")
        long_sma = params.get("long_sma", "")
        rsi_period = params.get("rsi_period", "")
        rsi_threshold = params.get("rsi_threshold", "")
        rsi_side = params.get("rsi_side", "")
        stop_loss = signal.get("stop_loss_pct", "")
        return " ".join(
            str(part)
            for part in [
                asset,
                hypothesis,
                f"short sma {short_sma}" if short_sma != "" else "",
                f"long sma {long_sma}" if long_sma != "" else "",
                f"rsi period {rsi_period}" if rsi_period != "" else "",
                f"rsi threshold {rsi_threshold}" if rsi_threshold != "" else "",
                f"rsi side {rsi_side}" if rsi_side else "",
                f"stop loss {stop_loss}" if stop_loss != "" else "",
                "empirical backtest out-of-sample transaction costs robustness",
            ]
            if str(part).strip()
        )

    def validate_params(self, params: dict[str, Any]) -> RSIParams:
        return RSIParams.model_validate(params)

    def prepare_market_data(self, raw_df: pl.DataFrame) -> pl.DataFrame:
        return raw_df.sort("timestamp")

    def simulate(self, close_prices, params: RSIParams):
        return get_equity_and_trades_rsi(
            close_prices,
            params.short_sma,
            params.long_sma,
            params.rsi_period,
            params.rsi_threshold,
            params.rsi_side,
        )

    def format_params(self, params: RSIParams) -> str:
        return (
            f"RSI Strategy: Short={params.short_sma}, Long={params.long_sma}, "
            f"RSI_Period={params.rsi_period}, RSI_Thresh={params.rsi_threshold}, RSI_Side={params.rsi_side}"
        )

    def build_execution_prompt(self, params: RSIParams, class_name: str) -> str:
        return f"""
Write a Freqtrade strategy using the following parameters:
- Strategy Type: SMA + RSI crossover
- Strategy Class Name: {class_name}
- Short SMA Window: {params.short_sma}
- Long SMA Window: {params.long_sma}
- RSI Period: {params.rsi_period}
- RSI Threshold: {params.rsi_threshold}
- RSI Side: {params.rsi_side}
- Timeframe: '1m'

The strategy should buy when the short SMA crosses above the long SMA and the RSI condition is met.
If rsi_side is 'below', buy when RSI is below the threshold. If it is 'above', buy when RSI is above the threshold.
It should sell when the short SMA crosses below the long SMA.

Use the `ta` or `qtpylib` library to populate indicators in `populate_indicators()`.
Implement entry logic in `populate_entry_trend()` and exit logic in `populate_exit_trend()`.
"""
