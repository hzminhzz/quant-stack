"""Standard backtesting interface for Smart DCA."""

from __future__ import annotations

import polars as pl
from pydantic import BaseModel, Field

from quant_stack.backtesting.costs import CostModel
from quant_stack.backtesting.metrics import calculate_metrics
from quant_stack.backtesting.results import BacktestResult
from quant_stack.strategies.smart_dca.adapter import run_smart_dca_backtest
from quant_stack.strategies.smart_dca.params import SmartDCAParams


class SmartDCABacktester(BaseModel):
    """Repo-standard wrapper for the Smart DCA simulator."""

    initial_capital: float = Field(10000.0, gt=0.0)
    cost_model: CostModel = Field(default_factory=CostModel)
    timestamp_col: str = "timestamp"
    bid_col: str | None = None
    ask_col: str | None = None
    close_col: str = "close"

    def run(self, df: pl.DataFrame, params: SmartDCAParams) -> BacktestResult:
        """Run the backtest and return a standard BacktestResult."""
        bid = self.bid_col if self.bid_col and self.bid_col in df.columns else self.close_col
        ask = self.ask_col if self.ask_col and self.ask_col in df.columns else self.close_col
        
        result = run_smart_dca_backtest(
            df=df,
            cfg=params,
            time_col=self.timestamp_col,
            bid_col=bid,
            ask_col=ask,
        )

        frame = pl.DataFrame({
            "timestamp": df[self.timestamp_col],
            "raw_equity": result["equity"],
            "realized_pnl": result["realized_pnl"],
            "open_pnl": result["open_pnl"],
            "net_lot": result["net_lot"],
        })

        frame = frame.with_columns(
            (pl.col("raw_equity") + self.initial_capital).alias("equity"),
            (pl.col("net_lot") > 0.0).alias("is_exposed")
        )

        metrics = calculate_metrics(frame, initial_capital=self.initial_capital)

        return BacktestResult(
            frame=frame,
            metrics=metrics,
            trades=[],
        )


__all__ = ["SmartDCABacktester"]
