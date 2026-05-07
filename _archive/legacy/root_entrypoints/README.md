# legacy/root_entrypoints/

This directory is for root-level compatibility entrypoints.

Current root-level compatibility surfaces:
- `research.py` - deprecated, use `quant_stack/cli/main research`
- `execution.py` - deprecated
- `pipeline_artifacts.py` - deprecated

Deleted (2025-05):
- `discovery.py` - removed, use external Gemini agent
- `live_swarm.py` - removed, use `quant_stack/research/optimization/`
- `engine/` - removed, use `quant_stack/backtesting/`
- `strategy_families/` - removed, use `quant_stack/strategies/`
- `evolution/` - removed
- `MLEvolve/` - removed

These root surfaces remain for compatibility only. New work should use `quant_stack/`.