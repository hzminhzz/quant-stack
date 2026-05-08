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
    cost_model: CostModel | None = None
    fill_policy: FillPolicy | None = None
    signal_column: str = "signal"
    price_column: str = "close"

    def run(self, df: pl.DataFrame) -> BacktestResult:
        cost_model = self.cost_model or CostModel(fee_rate=0.0, slippage_rate=0.0)
        fill_policy = self.fill_policy or FillPolicy(price="close_to_close", signal_lag_bars=1)
        if fill_policy.price != "close_to_close" or fill_policy.signal_lag_bars != 1:
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
                (pl.col("turnover") * cost_model.total_rate).alias("cost_return"),
            ]
        )
        frame = frame.with_columns((pl.col("gross_return") - pl.col("cost_return")).alias("net_return"))
        frame = frame.with_columns(((1.0 + pl.col("net_return")).cum_prod() * self.initial_capital).alias("equity"))
        frame = frame.with_columns((pl.col("position") > 0.0).alias("is_exposed"))
        metrics = calculate_metrics(frame, initial_capital=self.initial_capital)
        return BacktestResult(frame=frame, metrics=metrics, trades=_extract_trade_returns(frame))


def _extract_trade_returns(frame: pl.DataFrame) -> list[float]:
    trade_factors = (
        frame.select(
            [
                (pl.col("position") > 0.0).alias("in_trade"),
                (1.0 + pl.col("asset_return")).alias("bar_factor"),
            ]
        )
        .with_columns(
            [
                (
                    pl.col("in_trade")
                    & (~pl.col("in_trade").shift(1).fill_null(False))
                )
                .cast(pl.Int64)
                .cum_sum()
                .alias("trade_id")
            ]
        )
        .filter(pl.col("in_trade") & (pl.col("trade_id") > 0))
        .group_by("trade_id")
        .agg(pl.col("bar_factor").product().alias("trade_factor"))
        .sort("trade_id")
    )
    if trade_factors.is_empty():
        return []
    return [float(value) - 1.0 for value in trade_factors["trade_factor"].to_list()]


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"missing required backtest column(s): {', '.join(missing)}")


__all__ = ["PolarsSignalBacktester"]
