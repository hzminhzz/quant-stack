from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
import polars as pl

from engine.backtester_bb import get_equity_and_trades_bb
from strategy_families.base import StrategyFamily


class BBParams(BaseModel):
    bb_length: int = Field(20)
    bb_std: float = Field(1.0)
    regime_sma: int = Field(200)

    @field_validator("bb_length", "regime_sma")
    @classmethod
    def check_positive_windows(cls, value: int) -> int:
        if value <= 1:
            raise ValueError("Strategy periods must be greater than 1.")
        return value

    @field_validator("bb_std")
    @classmethod
    def check_std(cls, value: float) -> float:
        if value < 0.1 or value > 5.0:
            raise ValueError("StdDev must be between 0.1 and 5.0")
        return value


class BBSignal(BaseModel):
    asset: str = Field(..., description="Trading asset, e.g. BTC or ETH")
    params: BBParams
    hypothesis: str = Field(..., description="Short description of the breakout logic")
    stop_loss_pct: float = Field(2.5, description="Suggested stop loss percentage")


class BBStrategyFamily(StrategyFamily):
    name = "bb"
    raw_data_timeframe = "1m"
    validation_timeframe = "1h"

    def build_initial_prompt(self, seed_info: str) -> str:
        return (
            "Use `get_market_context` first, then propose a Bollinger Band breakout strategy. "
            "Return strategy_type='bb' and provide params for bb_length, bb_std, and regime_sma. "
            "Goal: maximize Smart Sharpe while keeping Max Drawdown under -16%. "
            "1-hour timeframe, 0.15% friction per side. Design for ROBUSTNESS and target 50+ trades in-sample. "
            + seed_info
        )

    def build_retry_prompt(self, critique: str) -> str:
        return (
            "The CRO rejected your last Bollinger Band strategy. Here is the critique:\n"
            + critique
            + "\nPropose a revised Bollinger Band strategy. Use get_market_context again if needed."
        )

    def build_seed_hint(self, signal: dict[str, object]) -> str:
        params = signal.get("params", {})
        return (
            f"The Alpha Researcher discovered a signal from paper '{signal.get('source', '?')}'. "
            f"Asset='{signal.get('asset', '?')}', hypothesis='{signal.get('hypothesis', '?')}', params={params}. "
            "Use it as a directional hypothesis only, but optimize a Bollinger Band family strategy around it."
        )

    def signal_model(self) -> type[BaseModel]:
        return BBSignal

    def build_discovery_prompt(self, raw_markdown: str, paper_context: str) -> str:
        return (
            "Extract a Bollinger Band breakout strategy signal from the source text. Return asset, params, hypothesis, and stop_loss_pct. "
            "Use params with fields bb_length, bb_std, and regime_sma. "
            "Use the source text as primary evidence and use retrieved support only as background.\n\n"
            "<source_text>\n"
            f"{raw_markdown}\n"
            "</source_text>\n\n"
            "<retrieved_support>\n"
            f"{paper_context}\n"
            "</retrieved_support>"
        )

    def build_paper_query(self, signal: dict[str, object]) -> str:
        params = signal.get("params", {}) if isinstance(signal, dict) else {}
        asset = str(signal.get("asset", "asset")).strip() if isinstance(signal, dict) else "asset"
        hypothesis = str(signal.get("hypothesis", "bollinger breakout strategy")).strip() if isinstance(signal, dict) else "bollinger breakout strategy"
        bb_length = params.get("bb_length", "")
        bb_std = params.get("bb_std", "")
        regime_sma = params.get("regime_sma", "")
        stop_loss = signal.get("stop_loss_pct", "") if isinstance(signal, dict) else ""
        return " ".join(
            str(part)
            for part in [
                asset,
                hypothesis,
                f"bollinger length {bb_length}" if bb_length != "" else "",
                f"bollinger std {bb_std}" if bb_std != "" else "",
                f"regime sma {regime_sma}" if regime_sma != "" else "",
                f"stop loss {stop_loss}" if stop_loss != "" else "",
                "empirical backtest out-of-sample transaction costs robustness",
            ]
            if str(part).strip()
        )

    def validate_params(self, params: dict[str, object]) -> BBParams:
        return BBParams.model_validate(params)

    def prepare_market_data(self, raw_df: pl.DataFrame) -> pl.DataFrame:
        return (
            raw_df.sort("timestamp")
            .group_by_dynamic("timestamp", every="1h")
            .agg([
                pl.col("open").first(),
                pl.col("high").max(),
                pl.col("low").min(),
                pl.col("close").last(),
                pl.col("volume").sum(),
            ])
        )

    def simulate(self, close_prices, params: BBParams):
        return get_equity_and_trades_bb(
            close_prices,
            params.bb_length,
            params.bb_std,
            params.regime_sma,
            friction=0.0015,
        )

    def format_params(self, params: BBParams) -> str:
        return f"BB Strategy: Length={params.bb_length}, StdDev={params.bb_std}, RegimeSMA={params.regime_sma}"

    def build_execution_prompt(self, params: BBParams, class_name: str) -> str:
        return f"""
Write a Freqtrade strategy using the following parameters:
- Strategy Type: Bollinger Band Breakout
- Strategy Class Name: {class_name}
- Bollinger Length: {params.bb_length}
- Bollinger StdDev: {params.bb_std}
- Regime SMA: {params.regime_sma}
- Timeframe: '1h'
- Friction assumption: 0.15% per side

The strategy should buy when price breaks above the upper Bollinger Band and is above the regime SMA.
It should sell when price falls below the Bollinger middle band.

Use the `ta` or `qtpylib` library to populate indicators in `populate_indicators()`.
Implement entry logic in `populate_entry_trend()` and exit logic in `populate_exit_trend()`.
"""
