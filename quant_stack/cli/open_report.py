"""Open the latest backtest report in browser."""

from __future__ import annotations

import argparse
import os
import subprocess
import webbrowser
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open latest backtest report")
    parser.add_argument("--latest", action="store_true", help="Open latest report (default)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    
    artifacts_dir = Path("artifacts")
    latest_link = artifacts_dir / "latest"
    
    if latest_link.is_symlink():
        report_path = latest_link.resolve() / "report.html"
        if report_path.exists():
            print(f"Opening: {report_path}")
            webbrowser.open(f"file://{report_path}")
        else:
            print(f"report.html not found in {latest_link.resolve()}")
    else:
        print("No latest symlink found. Run a backtest first.")


if __name__ == "__main__":
    main()