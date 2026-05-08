"""Unified canonical CLI dispatcher for quant_stack workflows."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable

CommandMain = Callable[[list[str] | None], object]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified quant_stack CLI")
    parser.add_argument(
        "command",
        choices=[
            "backtest",
            "experiment",
            "build-bybit-dataset",
            "research",
            "live-env",
            "walk-forward",
            "acceptance",
            "phase19",
            "inspect-data",
            "open-report",
            "api-tools",
        ],
        help="Canonical workflow command to run",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def _dispatch(command: str) -> CommandMain:
    mapping: dict[str, tuple[str, str]] = {
        "backtest": ("quant_stack.cli.run_backtest", "main"),
        "experiment": ("quant_stack.cli.run_strategy_experiment", "main"),
        "build-bybit-dataset": ("quant_stack.cli.build_bybit_dataset", "main"),
        "research": ("quant_stack.cli.run_research", "main"),
        "live-env": ("quant_stack.cli.run_live_env", "main"),
        "walk-forward": ("quant_stack.cli.run_walk_forward", "main"),
        "acceptance": ("quant_stack.cli.run_acceptance", "main"),
        "phase19": ("quant_stack.cli.run_phase19", "main"),
        "inspect-data": ("quant_stack.cli.inspect_data", "main"),
        "open-report": ("quant_stack.cli.open_report", "main"),
        "api-tools": ("quant_stack.cli.run_api_tools", "main"),
    }
    module_name, attr = mapping[command]
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    parsed = parser.parse_args(argv)
    fn = _dispatch(parsed.command)
    result = fn(parsed.args)
    if isinstance(result, int):
        return result
    return 0


__all__ = ["main"]
