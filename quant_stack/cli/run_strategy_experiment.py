"""CLI for Phase 18F baseline vs context strategy experiments."""

from __future__ import annotations

import argparse
import json

from quant_stack.research.experiments.config import load_params_json
from quant_stack.research.experiments.runner import run_strategy_experiment
from quant_stack.research.experiments.schemas import ExperimentConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a baseline vs context strategy experiment")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--start", default="1970-01-01T00:00:00")
    parser.add_argument("--end", default="2100-01-01T00:00:00")
    parser.add_argument("--train-start", default=None)
    parser.add_argument("--train-end", default=None)
    parser.add_argument("--test-start", default=None)
    parser.add_argument("--test-end", default=None)
    parser.add_argument("--walk-forward-enabled", action="store_true")
    parser.add_argument("--walk-forward-train-bars", type=int, default=None)
    parser.add_argument("--walk-forward-test-bars", type=int, default=None)
    parser.add_argument("--walk-forward-step-bars", type=int, default=None)
    parser.add_argument("--baseline-params", default=None)
    parser.add_argument("--context-params", default=None)
    parser.add_argument("--initial-cash", type=float, default=1.0)
    parser.add_argument("--fee-bps", type=float, default=0.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = ExperimentConfig(
        strategy_name=args.strategy,
        dataset_path=args.dataset,
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        train_start=args.train_start,
        train_end=args.train_end,
        test_start=args.test_start,
        test_end=args.test_end,
        walk_forward_enabled=args.walk_forward_enabled,
        walk_forward_train_bars=args.walk_forward_train_bars,
        walk_forward_test_bars=args.walk_forward_test_bars,
        walk_forward_step_bars=args.walk_forward_step_bars,
        baseline_params=load_params_json(args.baseline_params),
        context_params=load_params_json(args.context_params),
        initial_cash=args.initial_cash,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        output_dir=args.output_dir,
    )
    report = run_strategy_experiment(config)
    print(json.dumps({
        "strategy_name": report.strategy_name,
        "verdict": report.verdict,
        "output_dir": config.output_dir,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
