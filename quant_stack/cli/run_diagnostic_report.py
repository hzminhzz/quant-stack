"""Generate an ml4t-diagnostic tearsheet from backtest artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from quant_stack.reporting.ml4t_diagnostic import generate_ml4t_tearsheet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ml4t-diagnostic report HTML")
    parser.add_argument("--artifact-dir", required=True, help="Backtest artifact directory")
    parser.add_argument("--output-path", default=None, help="Optional output HTML path")
    parser.add_argument("--template", default="full", choices=["quant_trader", "hedge_fund", "risk_manager", "full"])
    parser.add_argument("--theme", default="default", choices=["default", "dark", "print", "presentation"])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = Path(args.artifact_dir)
    if not artifact_dir.exists():
        raise FileNotFoundError(f"Artifact directory not found: {artifact_dir}")
    output_path = Path(args.output_path) if args.output_path else artifact_dir / "ml4t_tearsheet.html"
    generate_ml4t_tearsheet(
        artifact_dir=artifact_dir,
        output_path=output_path,
        template=args.template,
        theme=args.theme,
    )
    print(f"ml4t diagnostic report written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
