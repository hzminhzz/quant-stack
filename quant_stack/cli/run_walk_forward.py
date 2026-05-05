"""Walk-forward CLI placeholder."""

from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run walk-forward validation")
    parser.add_argument("--data-path", required=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    _ = parse_args(argv)
    print("walk-forward command is scaffolded; implementation follows validation phase expansion")


if __name__ == "__main__":
    main()
