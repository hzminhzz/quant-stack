"""Adapters for ml4t-diagnostic artifact compatibility.

This module exports quant_stack backtest outputs into the artifact layout expected by
``ml4t.diagnostic.integration.backtest`` while preserving quant_stack core semantics.
"""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import polars as pl


def export_ml4t_diagnostic_artifacts(
    *,
    result_frame: pl.DataFrame,
    output_dir: Path,
    run_config: dict[str, Any],
    trades_df: pl.DataFrame | None,
) -> dict[str, Path]:
    """Write ml4t-compatible artifacts alongside native quant_stack artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    symbol = _infer_symbol(run_config)
    frame = result_frame.sort("timestamp")

    daily_returns_df = _daily_returns_from_result(frame)
    daily_returns_path = output_dir / "daily_returns.parquet"
    daily_returns_df.write_parquet(daily_returns_path)

    ml4t_trades = _ml4t_trades_from_quant_trades(trades_df, symbol=symbol)
    trades_path = output_dir / "trades.parquet"
    ml4t_trades.write_parquet(trades_path)

    equity_path = output_dir / "equity.parquet"
    frame.select(["timestamp", "equity"]).write_parquet(equity_path)

    weights_path = output_dir / "weights.parquet"
    frame.select(
        [
            pl.col("timestamp"),
            pl.lit(symbol).alias("symbol"),
            pl.col("position").cast(pl.Float64).alias("weight"),
        ]
    ).write_parquet(weights_path)

    portfolio_state_path = output_dir / "portfolio_state.parquet"
    frame.select(
        [
            pl.col("timestamp"),
            pl.col("equity").cast(pl.Float64).alias("equity"),
            pl.col("equity").cast(pl.Float64).alias("cash"),
            pl.col("position").abs().cast(pl.Float64).alias("gross_exposure"),
            pl.col("position").cast(pl.Float64).alias("net_exposure"),
            (pl.col("position") != 0.0).cast(pl.Int64).alias("open_positions"),
        ]
    ).write_parquet(portfolio_state_path)

    fills_path = output_dir / "fills.parquet"
    _fills_from_positions(frame, symbol=symbol).write_parquet(fills_path)

    spec_path = output_dir / "spec.json"
    spec = {
        "backtest_config": {
            "initial_cash": float(run_config.get("initial_capital", 10_000.0)),
            "metadata": {
                "strategy": run_config.get("strategy", "unknown"),
                "source": "quant_stack",
            },
        }
    }
    _ = spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    return {
        "daily_returns.parquet": daily_returns_path,
        "trades.parquet": trades_path,
        "equity.parquet": equity_path,
        "weights.parquet": weights_path,
        "portfolio_state.parquet": portfolio_state_path,
        "fills.parquet": fills_path,
        "spec.json": spec_path,
    }


def generate_ml4t_tearsheet(
    *,
    artifact_dir: Path,
    output_path: Path | None = None,
    template: str = "full",
    theme: str = "default",
) -> str:
    """Generate tearsheet HTML from an artifact directory using ml4t-diagnostic."""
    validate_ml4t_diagnostic_artifacts(artifact_dir)
    try:
        module = import_module("ml4t.diagnostic.integration.backtest")
        generate_tearsheet_from_run_artifacts = getattr(module, "generate_tearsheet_from_run_artifacts")
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(
            "ml4t-diagnostic is not installed. Install package 'ml4t-diagnostic' to enable tearsheets."
        ) from exc

    return generate_tearsheet_from_run_artifacts(
        backtest_dir=artifact_dir,
        output_path=output_path,
        template=template,
        theme=theme,
    )


def validate_ml4t_diagnostic_artifacts(artifact_dir: Path) -> None:
    """Validate minimal artifact contract expected by ml4t-diagnostic loaders."""
    required = ["trades.parquet", "daily_returns.parquet"]
    missing = [name for name in required if not (artifact_dir / name).exists()]
    if missing:
        raise ValueError(f"missing required diagnostic artifact(s): {', '.join(missing)}")

    trades = pl.read_parquet(artifact_dir / "trades.parquet")
    _require_columns(
        trades,
        ["symbol", "entry_time", "exit_time", "entry_price", "exit_price", "quantity", "pnl", "pnl_percent", "bars_held"],
        context="trades.parquet",
    )
    daily = pl.read_parquet(artifact_dir / "daily_returns.parquet")
    _require_columns(daily, ["date", "daily_return"], context="daily_returns.parquet")


def _require_columns(df: pl.DataFrame, required: list[str], *, context: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{context} missing required column(s): {', '.join(missing)}")


def _daily_returns_from_result(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame(schema={"date": pl.Date, "daily_return": pl.Float64})
    daily = (
        frame.group_by(pl.col("timestamp").dt.date().alias("date"))
        .agg([pl.col("equity").first().alias("open_eq"), pl.col("equity").last().alias("close_eq")])
        .sort("date")
    )
    return daily.select(
        [
            pl.col("date"),
            ((pl.col("close_eq") - pl.col("open_eq")) / pl.col("open_eq")).fill_nan(0.0).fill_null(0.0).alias("daily_return"),
        ]
    )


def _ml4t_trades_from_quant_trades(trades_df: pl.DataFrame | None, *, symbol: str) -> pl.DataFrame:
    schema = {
        "symbol": pl.Utf8,
        "entry_time": pl.Datetime("us"),
        "exit_time": pl.Datetime("us"),
        "entry_price": pl.Float64,
        "exit_price": pl.Float64,
        "quantity": pl.Float64,
        "pnl": pl.Float64,
        "pnl_percent": pl.Float64,
        "bars_held": pl.Int64,
    }
    if trades_df is None or trades_df.is_empty():
        return pl.DataFrame(schema=schema)
    required = {"entry_time", "exit_time", "entry_price", "exit_price", "pnl"}
    missing = required - set(trades_df.columns)
    if missing:
        return pl.DataFrame(schema=schema)
    return trades_df.select(
        [
            pl.lit(symbol).alias("symbol"),
            pl.col("entry_time").cast(pl.Datetime("us")).alias("entry_time"),
            pl.col("exit_time").cast(pl.Datetime("us")).alias("exit_time"),
            pl.col("entry_price").cast(pl.Float64).alias("entry_price"),
            pl.col("exit_price").cast(pl.Float64).alias("exit_price"),
            pl.lit(1.0).alias("quantity"),
            pl.col("pnl").cast(pl.Float64).alias("pnl"),
            pl.col("pnl").cast(pl.Float64).alias("pnl_percent"),
            pl.lit(1).cast(pl.Int64).alias("bars_held"),
        ]
    )


def _fills_from_positions(frame: pl.DataFrame, *, symbol: str) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame(
            schema={
                "order_id": pl.Utf8,
                "asset": pl.Utf8,
                "side": pl.Utf8,
                "quantity": pl.Float64,
                "price": pl.Float64,
                "timestamp": pl.Datetime("us"),
            }
        )
    fills = (
        frame.select(
            [
                pl.col("timestamp").cast(pl.Datetime("us")),
                pl.col("close").cast(pl.Float64).alias("price"),
                pl.col("position").cast(pl.Float64).alias("position"),
            ]
        )
        .with_columns((pl.col("position") - pl.col("position").shift(1).fill_null(0.0)).alias("delta"))
        .filter(pl.col("delta") != 0.0)
        .with_row_index("idx")
        .select(
            [
                pl.format("fill_{}", pl.col("idx")).alias("order_id"),
                pl.lit(symbol).alias("asset"),
                pl.when(pl.col("delta") > 0).then(pl.lit("buy")).otherwise(pl.lit("sell")).alias("side"),
                pl.col("delta").abs().alias("quantity"),
                pl.col("price"),
                pl.col("timestamp"),
            ]
        )
    )
    return fills


def _infer_symbol(run_config: dict[str, Any]) -> str:
    symbol = run_config.get("symbol")
    if isinstance(symbol, str) and symbol:
        return symbol
    data_path = run_config.get("data_path")
    if isinstance(data_path, str) and data_path:
        return Path(data_path).stem.upper()
    return "UNKNOWN"


__all__ = [
    "export_ml4t_diagnostic_artifacts",
    "generate_ml4t_tearsheet",
    "validate_ml4t_diagnostic_artifacts",
]
