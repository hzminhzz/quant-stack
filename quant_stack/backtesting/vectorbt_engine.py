"""Optional vectorbt adapter for path-dependent strategies."""

from __future__ import annotations

import polars as pl

from quant_stack.backtesting.costs import CostModel
from quant_stack.backtesting.metrics import calculate_metrics
from quant_stack.backtesting.results import BacktestResult


class VectorBTUnavailableError(ImportError):
    """Raised when vectorbt is requested but not installed."""


class VectorBTBacktester:
    """Thin adapter that isolates vectorbt and pandas from core APIs."""

    def __init__(
        self,
        *,
        initial_capital: float = 1.0,
        cost_model: CostModel | None = None,
        signal_column: str = "signal",
        sl_stop: float | None = None,
        tp_stop: float | None = None,
    ) -> None:
        self.initial_capital = initial_capital
        self.cost_model = cost_model or CostModel()
        self.signal_column = signal_column
        self.sl_stop = sl_stop
        self.tp_stop = tp_stop

    def run(self, df: pl.DataFrame, *, price: str = "close") -> BacktestResult:
        try:
            import vectorbt as vbt
        except ImportError as exc:
            raise VectorBTUnavailableError("vectorbt is optional; install the backtest extra before using VectorBTBacktester") from exc

        _require_columns(df, ["timestamp", price, self.signal_column])
        pandas_df = df.select(["timestamp", price, self.signal_column]).to_pandas()
        
        signal_series = pandas_df[self.signal_column].fillna(0.0).clip(0.0, 1.0)
        prev_signal = signal_series.shift(1).fillna(0.0)
        
        # 1-bar lag execution (signal at close of t-1 executes at close of t)
        entries = ((signal_series > 0) & (prev_signal == 0)).shift(1).fillna(False)
        exits = ((signal_series == 0) & (prev_signal > 0)).shift(1).fillna(False)
        
        kwargs = {}
        if self.sl_stop is not None:
            kwargs["sl_stop"] = self.sl_stop
        if self.tp_stop is not None:
            kwargs["tp_stop"] = self.tp_stop

        portfolio = vbt.Portfolio.from_signals(
            close=pandas_df[price],
            entries=entries,
            exits=exits,
            init_cash=self.initial_capital,
            fees=self.cost_model.total_rate,
            **kwargs
        )
        
        held_assets = portfolio.asset_flow().cumsum().to_numpy()
        position_mask = (held_assets > 1e-8).astype(float)
        
        frame = df.with_columns([
            pl.Series("equity", portfolio.value().to_numpy()),
            pl.Series("position", position_mask),
            pl.Series("is_exposed", position_mask > 0.0),
        ])
        
        metrics = calculate_metrics(frame, initial_capital=self.initial_capital)
        
        trades = []
        if portfolio.trades.count() > 0:
            records = portfolio.trades.records_readable
            if "Return" in records.columns:
                trades = records["Return"].tolist()
                
        return BacktestResult(frame=frame, metrics=metrics, trades=trades)


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"missing required vectorbt column(s): {', '.join(missing)}")


__all__ = ["VectorBTBacktester", "VectorBTUnavailableError"]
