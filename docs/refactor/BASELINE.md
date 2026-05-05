# Refactor Baseline

Date: 2026-05-05

## Scope

Phase 0 only. No architecture refactor, package move, indicator migration, or backtest engine replacement was performed.

## Repository shape

The current repo is a flat Python project with top-level orchestration modules and small packages:

```text
engine/
evolution/
strategy_families/
MLEvolve/
discovery.py
execution.py
live_swarm.py
pipeline_artifacts.py
research.py
validate_bb_strategy.py
validate_grid_strategy.py
test_*.py
pyproject.toml
uv.lock
```

There is no `quant_stack/` package yet. Current imports depend on root-level modules such as `engine`, `strategy_families`, and `live_swarm`, so Phase 1 must preserve compatibility while moving code into the new package structure.

## Baseline checks

### Python

```bash
uv run python --version
```

Result: `Python 3.11.15`

Plain `python` is not available in this environment; use `uv run python`.

### Tests

```bash
uv run pytest
```

Result: failed before test collection.

Failure summary:

```text
ModuleNotFoundError: No module named 'antlr4'
```

The failure occurs while pytest loads the `hydra` plugin, which imports `omegaconf`, which imports `antlr4`. No project tests were collected or executed.

### Compile check

Initial command:

```bash
uv run python -m compileall .
```

Result: timed out because it traversed `.venv`.

Repo-focused command:

```bash
uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .
```

Result: passed with no output.

## Secret scan

Command pattern used:

```text
api_key\s*=|sk-[A-Za-z0-9]{16,}|DEEPSEEK|OPENAI_API_KEY|secret|token
```

High-risk hardcoded DeepSeek-style keys were found in:

```text
live_swarm.py
test_deepseek.py
test_swarm_agent.py
```

These were removed in Phase 0 and replaced with `DEEPSEEK_API_KEY` environment loading.

Placeholder/non-secret API key values remain where they target local OpenAI-compatible services:

```text
live_swarm.py          api_key="anything" for local fallback
discovery.py           api_key="anything" for local provider
research.py            api_key="anything" for local provider
execution.py           api_key='anything' for local provider
```

## Security action required

The exposed DeepSeek-style key must be treated as compromised. Rotate/revoke it at the provider before using `DEEPSEEK_API_KEY` again.

## Existing uncommitted changes outside Phase 0

Before Phase 0 edits, git status already showed:

```text
M mass_fetch_historical.py
```

That file was not touched during Phase 0.
