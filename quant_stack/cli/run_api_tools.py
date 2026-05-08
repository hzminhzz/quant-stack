"""CLI wrappers for quant_stack API tool bridge."""

from __future__ import annotations

import argparse
import json

from quant_stack.api.tools import artifact_fetch_summary, backtest_batch, backtest_run, strategy_describe, strategy_list


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run quant_stack API bridge tools")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("strategy-list", help="List available strategies")

    describe = subparsers.add_parser("strategy-describe", help="Describe one strategy")
    describe.add_argument("--strategy", required=True)

    run_single = subparsers.add_parser("backtest-run", help="Run one backtest from JSON payload")
    run_single.add_argument("--payload-json", required=True)

    run_batch = subparsers.add_parser("backtest-batch", help="Run batch backtest from JSON payload")
    run_batch.add_argument("--payload-json", required=True)

    fetch = subparsers.add_parser("artifact-fetch-summary", help="Fetch summary JSON artifact")
    fetch.add_argument("--summary-path", required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.subcommand == "strategy-list":
        print(json.dumps(strategy_list(), indent=2, sort_keys=True))
        return
    if args.subcommand == "strategy-describe":
        print(json.dumps(strategy_describe(args.strategy), indent=2, sort_keys=True))
        return
    if args.subcommand == "backtest-run":
        payload = json.loads(args.payload_json)
        print(json.dumps(backtest_run(payload), indent=2, sort_keys=True))
        return
    if args.subcommand == "backtest-batch":
        payload = json.loads(args.payload_json)
        print(json.dumps(backtest_batch(payload), indent=2, sort_keys=True))
        return
    if args.subcommand == "artifact-fetch-summary":
        print(json.dumps(artifact_fetch_summary(args.summary_path), indent=2, sort_keys=True))
        return
    raise ValueError(f"unknown subcommand: {args.subcommand}")


if __name__ == "__main__":
    main()
