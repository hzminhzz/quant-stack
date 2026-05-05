"""Optional vectorbt adapter for path-dependent strategies."""

from __future__ import annotations

import polars as pl

from quant_stack.backtesting.results import BacktestResult


class VectorBTUnavailableError(ImportError):
    """Raised when vectorbt is requested but not installed."""


class VectorBTBacktester:
    """Thin adapter that isolates vectorbt and pandas from core APIs."""

    def __init__(self, *, init_cash: float = 1.0, fees: float = 0.0) -> None:
        self.init_cash = init_cash
        self.fees = fees

    def run(self, df: pl.DataFrame, *, entries: str = "entry_signal", exits: str = "exit_signal", price: str = "close") -> BacktestResult:
        try:
            import vectorbt as vbt
        except ImportError as exc:
            raise VectorBTUnavailableError("vectorbt is optional; install the backtest extra before using VectorBTBacktester") from exc

        _require_columns(df, [price, entries, exits])
        pandas_df = df.select([price, entries, exits]).to_pandas()
        portfolio = vbt.Portfolio.from_signals(
            close=pandas_df[price],
            entries=pandas_df[entries].astype(bool),
            exits=pandas_df[exits].astype(bool),
            init_cash=self.init_cash,
            fees=self.fees,
        )
        frame = df.with_columns(pl.Series("equity", portfolio.value().to_numpy()))
        return BacktestResult(frame=frame, metrics={"total_return": float(portfolio.total_return())}, trades=[])


def _require_columns(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"missing required vectorbt column(s): {', '.join(missing)}")


__all__ = ["VectorBTBacktester", "VectorBTUnavailableError"]
