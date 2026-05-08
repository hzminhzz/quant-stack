"""CLI for running a quant_stack Polars signal backtest.

Optimized for cost control:
- Use --start/--end to filter data (don't load full dataset into LLM context)
- Output goes to artifacts/ directory with consistent structure
- Use summary.json for results, not raw data
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import polars as pl
from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.data import load_ohlcv_parquet
from quant_stack.reporting.backtest_report import GateConfig, ReportPolicy, write_backtest_artifacts
from quant_stack.strategies import get_strategy
from quant_stack.strategies.specs import validate_engine_compatibility


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a quant_stack Polars signal backtest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-path", required=True, help="Path to OHLCV parquet file")
    parser.add_argument("--strategy", default="rsi_sma", help="Strategy name")
    parser.add_argument("--params-json", default="{}", help="Strategy params as JSON string")
    parser.add_argument("--fee-rate", type=float, default=0.0, help="Fee rate (0.001 = 0.1%%)")
    parser.add_argument(
        "--start",
        default=None,
        help="Start date (YYYY-MM-DD). Filters data before processing.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="End date (YYYY-MM-DD). Filters data before processing.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for artifacts. Default: artifacts/{strategy}_{symbol}_{start}_{end}",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10000.0,
        help="Initial capital for backtest",
    )
    parser.add_argument(
        "--report-policy",
        type=str,
        default="pass_only",
        choices=["pass_only", "always", "never"],
        help="When to generate HTML report: pass_only (default), always, or never",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=30,
        help="Minimum trades required to pass gate (default: 30)",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=0.25,
        help="Maximum drawdown threshold (default: 0.25 = 25%%)",
    )
    return parser.parse_args(argv)


def _filter_by_date(df, start: str | None, end: str | None):
    if start is None and end is None:
        return df
    ts_col = "timestamp"
    if start:
        df = df.filter(pl.col(ts_col) >= datetime.fromisoformat(start))
    if end:
        df = df.filter(pl.col(ts_col) <= datetime.fromisoformat(end))
    return df


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    df = load_ohlcv_parquet(args.data_path, validate=True)
    df = _filter_by_date(df, args.start, args.end)

    strategy = get_strategy(args.strategy)
    validate_engine_compatibility(strategy.spec, "polars")
    params = strategy.validate_params(json.loads(args.params_json))
    signals = strategy.build_signals(df, params)

    cost_model = CostModel(fee_rate=args.fee_rate, slippage_rate=0.0)
    result = PolarsSignalBacktester(initial_capital=args.initial_capital, cost_model=cost_model).run(signals)

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        data_name = Path(args.data_path).stem
        start_str = args.start.replace("-", "") if args.start else "all"
        end_str = args.end.replace("-", "") if args.end else "all"
        out_dir = Path("artifacts") / f"{args.strategy}_{data_name}_{start_str}_{end_str}"

    run_config = {
        "data_path": args.data_path,
        "strategy": args.strategy,
        "params": params.model_dump(),
        "fee_rate": args.fee_rate,
        "start": args.start,
        "end": args.end,
        "initial_capital": args.initial_capital,
        "rows_used": len(df),
    }

    gate_config = GateConfig(
        min_trades=args.min_trades,
        max_drawdown_pct=args.max_drawdown,
        report_policy=ReportPolicy(args.report_policy),
    )

    artifacts = write_backtest_artifacts(
        result_frame=result.frame,
        metrics=result.metrics,
        run_config=run_config,
        output_dir=out_dir,
        title=f"{args.strategy} Backtest",
        gate_config=gate_config,
    )

    latest_link = Path("artifacts") / "latest"
    if latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(out_dir.name)

    print(f"Results saved to {out_dir}/")
    for name in sorted(artifacts.keys()):
        print(f"  - {name}")
    print(f"\nOpen report: xdg-open {out_dir}/report.html")
    print(f"Or use: uv run python -m quant_stack.cli.main open-report")


if __name__ == "__main__":
    main()
