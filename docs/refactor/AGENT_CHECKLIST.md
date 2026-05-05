# Agent Checklist

> Quick reference for agents working on quant-stack.

## Pre-Work
- [ ] Read `AGENTS.md` (repo root)
- [ ] Understand core philosophy: deterministic first, LLM for planning not execution
- [ ] Identify which paths are "core" vs "allowed"

## Core Paths (Forbidden to Add)
- `quant_stack/backtesting/` - No pandas, no LLM, no strategy-specific
- `quant_stack/indicators/` - No LLM, no external API calls
- `quant_stack/live/tick_loop` - No LLM, no blocking I/O

## Allowed Paths
- `quant_stack/research/` - LLM-powered, optimization
- `quant_stack/strategies/` - Strategy implementations
- `quant_stack/intelligence/` - Market data gathering
- `quant_stack/workflows/` - Workflow orchestration

## Import Rules
| Module | Pandas | LLM (pydantic_ai/openai/anthropic) | Strategy-specific |
|--------|--------|-----------------------------------|-------------------|
| backtesting | ❌ | ❌ | ❌ |
| indicators | ❌ | ❌ | ❌ |
| live/tick | ❌ | ❌ | ❌ |
| research | ✅ | ✅ | N/A |
| intelligence | ❌ | ❌ | N/A |
| strategies | ❌ | ❌ | ✅ |

## Testing
After any import change:
```bash
uv run pytest tests/architecture/test_architecture_boundaries.py -q
```

## Forbidden Patterns (Memorize)
1. No `run_rsi_backtest()`, `run_bb_backtest()` in backtesting module
2. No `import pandas` in core paths
3. No `from pydantic_ai import Agent` in backtesting/indicators/live
4. No `api_secret`, `private_key`, `password` in research code
5. No live broker connections in research tasks
6. No order-placement imports in research/intelligence

## Legacy Handling
- `legacy/` and `strategy_families/` are deprecated
- Don't import from legacy into new core code
- Don't move legacy to core paths

## Artifact Rules
- Research artifacts → `artifacts/{experiment_name}/`
- Manifest: `timestamp: null`, `output_dir: "."`
- Optimization requests: always `status: "proposed"`

## Workflow
1. Read AGENTS.md
2. Plan work respecting boundaries
3. Execute
4. Run architecture tests
5. Report results