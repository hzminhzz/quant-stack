"""CLI for checking live environment requirements."""

from __future__ import annotations

import argparse

from quant_stack.live import require_env


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check required live environment variables")
    parser.add_argument("--required", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    for name in args.required:
        require_env(name)
    print("live environment check passed")


if __name__ == "__main__":
    main()
