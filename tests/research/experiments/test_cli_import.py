from __future__ import annotations


def test_cli_import_no_side_effects() -> None:
    import quant_stack.cli.run_strategy_experiment as mod

    assert hasattr(mod, "main")
    assert hasattr(mod, "parse_args")
