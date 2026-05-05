"""CLI for running a simple quant_stack Polars signal backtest."""

from __future__ import annotations

import argparse
import json

from quant_stack.backtesting import CostModel, PolarsSignalBacktester
from quant_stack.data import load_ohlcv_parquet
from quant_stack.strategies import get_strategy


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a quant_stack Polars signal backtest")
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--strategy", default="rsi_sma")
    parser.add_argument("--params-json", default="{}")
    parser.add_argument("--fee-rate", type=float, default=0.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    strategy = get_strategy(args.strategy)
    params = strategy.validate_params(json.loads(args.params_json))
    df = load_ohlcv_parquet(args.data_path)
    signals = strategy.build_signals(df, params)
    result = PolarsSignalBacktester(cost_model=CostModel(fee_rate=args.fee_rate)).run(signals)
    print(json.dumps(result.metrics, indent=2, default=str))


if __name__ == "__main__":
    main()
