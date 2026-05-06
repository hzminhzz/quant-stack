#!/usr/bin/env python
"""Run Phase 19 autonomous research pipeline for MACD-TD V6."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quant_stack.research.phase_orchestration.phase19_runner import run_phase19_pipeline


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python run_phase19_macd_td_auto.py <config_yaml_path>")
        return 1

    config_path = Path(sys.argv[1])

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1

    print(f"Starting Phase 19 autonomous pipeline...")
    print(f"Config: {config_path}")

    status = run_phase19_pipeline(config_path)

    print("\n" + "=" * 50)
    print("Pipeline Execution Complete")
    print("=" * 50)
    print(f"Pipeline ID: {status.pipeline_id}")
    print(f"Completed phases: {status.completed_phases}")
    print(f"Failed phase: {status.failed_phase or 'None'}")
    print(f"Stop reason: {status.stop_reason or 'Completed all enabled phases'}")
    print(f"Final verdict: {status.final_verdict}")
    print("=" * 50)

    if status.failed_phase:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())