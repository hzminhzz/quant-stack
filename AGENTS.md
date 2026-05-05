# quant-stack Agent Governance

## Core Philosophy
- **Deterministic first**: Core engines (backtesting, indicators, live tick processing) must be pure, deterministic, and testable without external dependencies.
- **LLMs for planning, not execution**: Use LLMs for research planning, idea generation, and critique—but never inside deterministic trading engines.
- **Strategy-agnostic core**: The `quant_stack/backtesting` module provides generic backtest infrastructure. Strategy-specific logic lives in `quant_stack/strategies/` or `strategy_families/`.
- **No pandas in core**: Core paths (`quant_stack/backtesting`, `quant_stack/indicators`, `quant_stack/live` tick loops) must use Polars or native Python. Pandas is allowed only in research/optimization exploration scripts.
- **No Polars in live tick step**: Live tick processing must use native Python or Polars without complex transformations. Keep it simple and fast.

## Architecture Boundaries

### Allowed
- `quant_stack/research/` - LLM-powered research, optimization, experiment orchestration
- `quant_stack/strategies/` - Strategy implementations (rsi_sma, bb_breakout, grid, etc.)
- `quant_stack/intelligence/` - Market intelligence gathering (OKX sources, scoring, normalization)
- `quant_stack/workflows/` - Workflow orchestration (actions, triggers, cooldown)

### Forbidden in Core
- `quant_stack/backtesting/` - No strategy-specific backtesters, no LLM imports, no pandas
- `quant_stack/indicators/` - No LLM imports, no external API calls
- `quant_stack/live/tick_loop` - No LLM calls, no blocking I/O, no complex transformations

## Forbidden Patterns
1. **No pandas in core paths** - `quant_stack/backtesting/*.py`, `quant_stack/indicators/*.py`, `quant_stack/live/*.py`
2. **No LLM in deterministic engines** - Don't import pydantic_ai, openai, anthropic in backtesting/indicators/live
3. **No strategy-specific backtesters** - Don't add `run_rsi_backtest()`, `run_bb_backtest()` to `polars_engine.py`
4. **No live trading by default** - Research tasks must work without credentials or live broker connections
5. **No order-placement in research** - Don't import execution/broker modules in research/intelligence paths
6. **No private-key terms in research** - Don't have `api_secret`, `private_key`, `password` in research code

## Strategy Experiment Workflow
1. Define hypothesis in YAML (see `examples/pipeline_queries/`)
2. Generate deterministic fixtures (see `quant_stack/research/fixtures.py`)
3. Run baseline vs candidate with context gating
4. Validate no-lookahead, no-future-leakage
5. Artifact output includes proposed-only optimization record (never auto-executed)

## Legacy Code Policy
- `legacy/` - Deprecated code, do not extend
- `strategy_families/` - Legacy pattern, prefer `quant_stack/strategies/`
- Do not move legacy modules to core paths
- Do not import legacy modules in new core code

## Artifact Policy
- Research artifacts go to `artifacts/{experiment_name}/`
- Manifest always includes `timestamp: null` and `output_dir: "."` for determinism
- Optimization requests are always `status: "proposed"` - never auto-execute

## Testing Expectations
- All new code requires tests in `tests/`
- Architecture boundary tests in `tests/architecture/test_architecture_boundaries.py`
- Run: `uv run pytest tests/architecture/test_architecture_boundaries.py -q`

## Agent Execution Protocol
1. Read `AGENTS.md` before any work
2. Check architecture boundaries before adding imports
3. Run architecture tests after any import changes
4. Never modify trading logic without explicit user request
5. Never add live execution without explicit user request