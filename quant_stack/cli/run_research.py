"""CLI for creating a non-authoritative research artifact."""

from __future__ import annotations

import argparse
import json

from quant_stack.artifacts import save_artifact
from quant_stack.research import build_research_artifact


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a quant_stack research artifact")
    parser.add_argument("--strategy-type", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--params-json", default="{}")
    parser.add_argument("--output", default="artifacts/quant_stack_research.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    artifact = build_research_artifact(
        strategy_type=args.strategy_type,
        hypothesis=args.hypothesis,
        params=json.loads(args.params_json),
    )
    save_artifact(artifact, args.output)
    print(f"saved research artifact to {args.output}")


if __name__ == "__main__":
    main()
