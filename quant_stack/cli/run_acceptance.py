"""CLI wrapper for the Phase 17 acceptance workflow."""

from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phase 17 acceptance workflow")
    parser.add_argument("--query", required=True, help="Path to an acceptance query YAML file")
    parser.add_argument("--output-dir", required=True, help="Directory for JSON and markdown artifacts")
    parser.add_argument("--fixture-root", default=None, help="Optional root for persisted deterministic OHLCV fixtures")
    parser.add_argument("--intelligence-root", default=None, help="Optional root for persisted deterministic intelligence events")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        from quant_stack.workflows.acceptance import run_acceptance_query
    except ImportError as exc:
        raise RuntimeError(
            "Acceptance workflow dependencies are not currently importable through the canonical path. "
            "The legacy acceptance harness still needs compatibility repair before full migration."
        ) from exc

    try:
        run_acceptance_query(
            args.query,
            output_dir=args.output_dir,
            fixture_root=args.fixture_root,
            intelligence_root=args.intelligence_root,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Acceptance workflow execution still depends on a legacy harness path that is not currently importable. "
            "Compatibility repair is still required before this command becomes fully canonical."
        ) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
