"""CLI wrapper for the Phase 19 orchestration workflow."""

from __future__ import annotations

import argparse

from quant_stack.workflows.phase19 import run_phase19


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase 19 orchestration workflow")
    parser.add_argument("config_yaml_path", help="Path to the Phase 19 config YAML")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = run_phase19(args.config_yaml_path)
    print(f"Pipeline ID: {status.pipeline_id}")
    print(f"Completed phases: {status.completed_phases}")
    print(f"Failed phase: {status.failed_phase or 'None'}")
    print(f"Final verdict: {status.final_verdict}")
    return 1 if status.failed_phase else 0


if __name__ == "__main__":
    raise SystemExit(main())
