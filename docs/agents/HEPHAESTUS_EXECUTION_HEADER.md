# Hephaestus Execution Header

> Standard header to prepend to agent execution briefs.

---

## Governance Check

Before executing any task, verify:

1. **Read AGENTS.md** → `cat AGENTS.md` or `head -50 AGENTS.md`
2. **Check boundaries** → Does this touch forbidden paths?
   - `quant_stack/backtesting/` - no LLM, no pandas, no strategy-specific
   - `quant_stack/indicators/` - no LLM, no API calls
   - `quant_stack/live/` - no LLM in tick loops
3. **Run architecture tests** → `uv run pytest tests/architecture/test_architecture_boundaries.py -q`

## Scope Guardrails

| Action | Allowed? |
|--------|----------|
| Modify trading logic | ❌ Only if explicitly requested |
| Modify backtest semantics | ❌ Only if explicitly requested |
| Modify optimizer behavior | ❌ Only if explicitly requested |
| Add live execution | ❌ Only if explicitly requested |
| Move legacy modules | ❌ Never |
| Use pandas in core | ❌ Never |
| Use LLM in deterministic engines | ❌ Never |
| Add credentials/API keys | ❌ Never in research |

## Report Format

When complete, report:
1. files created
2. files modified
3. tests added
4. tests run
5. failures
6. limitations
7. recommended next task

---