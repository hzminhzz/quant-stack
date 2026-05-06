#!/usr/bin/env python
"""Run MACD-TD V6 strategy intake pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quant_stack.research.strategy_intake.macd_td_v6_intake import generate_artifacts


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python run_macd_td_v6_intake.py <query_yaml_path>")
        return 1

    query_path = Path(sys.argv[1])

    if not query_path.exists():
        print(f"Error: Query file not found: {query_path}")
        return 1

    artifacts = generate_artifacts(query_path, "artifacts/research/macd_td_v6_intake_v1")

    print("Artifacts generated:")
    for name, path in artifacts.items():
        print(f"  {name}: {path}")

    print("\nPhase 19A intake complete.")
    print("Review artifacts in artifacts/research/macd_td_v6_intake_v1/")

    return 0


if __name__ == "__main__":
    sys.exit(main())