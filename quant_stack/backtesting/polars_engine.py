"""Simple Polars signal backtester with explicit no-lookahead semantics."""

from __future__ import annotations

import polars as pl
from pydantic import BaseModel, Field

from quant_stack.backtesting.costs import CostModel
from quant_stack.backtesting.fills import FillPolicy
from quant_stack.backtesting.metrics import calculate_metrics
from quant_stack.backtesting.results import BacktestResult


class PolarsSignalBacktester(BaseModel):
    """Backtest long/flat signal streams with close-to-close returns."""

    initial_capital: float = Field(1.0, gt=0.0)
    cost_model: CostModel = Field(default_factory=CostModel)
    fill_policy: FillPolicy = Field(default_factory=FillPolicy)
    signal_column: str = "signal"
    price_column: str = "close"

    def run(self, df: pl.DataFrame) -> BacktestResult:
        if self.fill_policy.price != "close_to_close" or self.fill_policy.signal_lag_bars != 1:
            raise NotImplementedError("PolarsSignalBacktester currently supports close_to_close fills with a one-bar signal lag")
        _require_columns(df, ["timestamp", self.price_column, self.signal_column])
        frame = df.sort("timestamp").with_columns(
            [
                pl.col(self.signal_column).cast(pl.Float64).fill_null(strategy="forward").fill_null(0.0).clip(0.0, 1.0).alias("target_position"),
                pl.col(self.price_column).pct_change().fill_null(0.0).alias("asset_return"),
            ]
        )
        frame = frame.with_columns(pl.col("target_position").shift(1).fill_null(0.0).alias("position"))
        frame = frame.with_columns((pl.col("position") - pl.col("position").shift(1).fill_null(0.0)).abs().alias("turnover"))
        frame = frame.with_columns(
            [
                (pl.col("position") * pl.col("asset_return")).alias("gross_return"),
                (pl.col("turnover") * self.cost_model.total_rate).alias("cost_return"),
            ]
        )
        frame = frame.with_columns((pl.col("gross_return") - pl.col("cost_return")).alias("net_return"))
        frame = frame.with_columns(((1.0 + pl.col("net_return")).cum_prod() * self.initial_capital).alias("equity"))
        frame = frame.with_columns((pl.col("position") > 0.0).alias("is_exposed"))
        metrics = calculate_metrics(frame, initial_capital=self.initial_capital)
        return BacktestResult(frame=frame, metrics=metrics, trades=_extract_trade_returns(frame))


def _extract_trade_returns(frame: pl.DataFrame) -> list[float]:
    rows = frame.select(["position", "asset_return"]).to_dicts()
    trades: list[float] = []
    current = 1.0
    in_trade = False
    for row in rows:
        position = float(row["position"])
        if position > 0.0:
            in_trade = True
            current *= 1.0 + float(row["asset_return"])
        elif in_trade:
            trades.append(current - 1.0)
            current = 1.0
            in_trade = False
    if in_trade:
        trades.append(current - 1.0)
    return trades


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"missing required backtest column(s): {', '.join(missing)}")


__all__ = ["PolarsSignalBacktester"]
