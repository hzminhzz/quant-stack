# Prometheus Plan Template

> Template for agent work plans that enforce quant-stack architecture boundaries.

## Mission
[One sentence describing the goal]

## Constraints & Preferences
- [ ] Read `AGENTS.md` before any work
- [ ] Check architecture boundaries before adding imports
- [ ] Run `uv run pytest tests/architecture/test_architecture_boundaries.py -q` after any import changes

## Progress
### Done
- [list completed items]

### In Progress
- [list items being worked on]

### Blocked
- [list blockers]

## Key Decisions
- [document important architectural choices]

## Next Steps
- [actionable next items]

## Critical Context
- **Files**: [list key files being modified]
- **Code in Progress**: [describe current code state]
- **State & Variables**: [any important runtime state]
- **External References**: [any external docs/libs]

## Explicit Constraints (Verbatim Only)
- Do not add new strategy logic
- Do not improve the optimizer
- Do not add live trading
- Do not modify broker/execution/risk modules
- Do not use real API credentials
- Do not require OKX credentials
- Do not use pandas in core
- STOP after [scope]

## Agent Verification State
- **Current Agent**: [name]
- **Verification Progress**: [status]
- **Acceptance Status**: [approved/pending/rejected]

## Delegated Agent Sessions
- [list any subagent sessions]