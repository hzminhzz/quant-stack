"""Thin compatibility wrapper for the canonical Phase 17 acceptance workflow."""

from __future__ import annotations

from quant_stack.workflows.acceptance_impl import main, parse_args, run_acceptance

__all__ = ["main", "parse_args", "run_acceptance"]


if __name__ == "__main__":
    main()
