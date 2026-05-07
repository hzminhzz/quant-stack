# scripts/

This directory is for **thin operational entrypoints only**.

## Rule

Scripts should:

- parse CLI arguments,
- call canonical package functions,
- write user-facing output,
- preserve old command compatibility during migration.

Scripts should **not** become the permanent home for new backtesting, optimization,
reporting, or orchestration logic.

If a script contains substantial business logic today, treat it as a migration target
to be wrapped or moved later while keeping the old entrypoint working.
