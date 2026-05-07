# Repo Structure Migration Plan

## 1. Executive Summary

The repository is in a **half-migrated** state.

- `quant_stack/` is clearly the intended canonical reusable package. It already contains real backtesting, strategies, data, features, intelligence, research, live, CLI, and workflow code.
- At the same time, older active systems still exist at top level: `engine/`, `strategy_families/`, `evolution/`, root `research.py`, root `discovery.py`, `pipeline_artifacts.py`, `live_swarm.py`, and root `validate_*.py`.
- `legacy/` exists, but much of the actual legacy surface has **not** been moved there yet. That makes the repo misleading: the folder named `legacy/` is not the true boundary of legacy code.
- The top-level `README.md` is centered on paper-search and root research scripts, while `AGENTS.md` says `quant_stack/` is the canonical system. That mismatch alone is enough to confuse agents.

### What seems canonical

- `quant_stack/backtesting/`
- `quant_stack/strategies/`
- `quant_stack/data/`
- `quant_stack/features/`
- `quant_stack/workflows/`
- `quant_stack/research/` and its typed orchestration / experiment / optimization modules
- `tests/architecture/` and most of `tests/`

### What seems legacy or ambiguous

- `engine/` remains a working alternate backtesting/evaluation system.
- `strategy_families/` remains a working alternate strategy abstraction layer.
- `evolution/` is still an active dependency for root research / artifact surfaces.
- `scripts/` contains a mix of thin wrappers and substantive one-off experiment logic.
- root `research.py`, `discovery.py`, `pipeline_artifacts.py`, `validate_*.py`, and `live_swarm.py` continue to advertise non-canonical workflows.

### Why agents are confused

1. **Two or more ways to do the same thing** are visible at the same time.
2. **Legacy code is still live at root**, not isolated under `legacy/`.
3. **Scripts are not consistently thin wrappers**.
4. **Artifacts, reports, and data roots are split** across `artifacts/`, `reports/`, `data/`, `Data/`, `Binance/`, `lancedb/`, etc.
5. **Tests still encode both eras**: canonical `quant_stack` and older `engine` / `strategy_families` paths.

### Target direction

The target structure should make one thing obvious:

> `quant_stack/` is the only package agents should extend by default.

Root should be mostly:

- project metadata (`pyproject.toml`, `README.md`, `AGENTS.md`)
- thin operational wrappers (`scripts/`)
- tests/docs/examples/configs
- local/generated state (`data/`, `artifacts/`)
- clearly marked `legacy/` systems

---

## 2. Current Structure Map

| Path | Current role | Canonical? | Risk level | Notes |
|---|---|---|---|---|
| `quant_stack/` | Main reusable Python package | Canonical | Medium | Real package, but still coexists with alternate root-level systems. |
| `quant_stack/backtesting/` | Standardized engines, metrics, contracts, results | Canonical | Low | Exports `BacktestResult`, `PolarsSignalBacktester`, `CostModel`, `FillPolicy`, `calculate_metrics`. |
| `quant_stack/strategies/` | Canonical strategy modules and registry | Canonical | Low | Contains `StrategyRegistry` and `StrategyModule`; this should be the main strategy entrypoint. |
| `quant_stack/data/` | Canonical data validation/load/resample and Bybit dataset helpers | Canonical | Low | Strong package candidate; aligned with AGENTS.md policy. |
| `quant_stack/features/` | Canonical feature pipeline and validation | Canonical | Low | High-value canonical surface for agents. |
| `quant_stack/indicators/` | Canonical indicators | Canonical | Low | Core path with architecture constraints. |
| `quant_stack/intelligence/` | Canonical context/intelligence package | Canonical | Medium | Useful but research-adjacent; should not leak into deterministic core improperly. |
| `quant_stack/live/` | Canonical live-state package | Canonical | Medium | Canonical, but high-risk area because live semantics are sensitive. |
| `quant_stack/workflows/` | Canonical workflow/event routing layer | Canonical | Medium | Already exists, but not yet the single orchestrator for all repo workflows. |
| `quant_stack/research/` | Typed research, experiments, acceptance, optimization, orchestration | Canonical | Medium | Important package, but it currently also absorbs what could later become `quant_stack/optimization/` and `quant_stack/reporting/`. |
| `quant_stack/research/optimization/` | Canonical-ish optimization/CRO loop today | Ambiguous | Medium | Operationally canonical today, but target structure suggests promotion to `quant_stack/optimization/`. |
| `quant_stack/artifacts/` | Canonical artifact schemas/store | Canonical | Low | Good package surface; underused compared with root `pipeline_artifacts.py`. |
| `quant_stack/cli/` | CLI entrypoints | Operational | Medium | Some files are thin wrappers; repo still lacks one unified canonical CLI surface. |
| `quant_stack/optimization/` | Not present | Ambiguous | Low | Optimization exists under `quant_stack/research/optimization/` instead. |
| `quant_stack/reporting/` | Not present | Ambiguous | Low | Reporting exists in scattered helpers under `quant_stack/research/` and root artifacts/report files. |
| `engine/` | Old backtest/evaluator/analytics system | Legacy | High | Very dangerous because it still looks usable and is imported broadly. |
| `evolution/` | Legacy/experimental evolution memory and research guard types | Experimental | High | Still imported by root artifact/research flows; not safely isolated. |
| `strategy_families/` | Old strategy-family abstraction tied to old workflow | Legacy | High | Agents can easily copy this by mistake instead of `quant_stack/strategies/`. |
| `legacy/` | Placeholder legacy namespace | Legacy | Medium | Conceptually correct, but incomplete: much real legacy code still lives outside it. |
| `scripts/` | Operational wrappers plus one-off experiment runners | Operational | High | Mixed role; some are thin wrappers, many contain substantive research logic. |
| `research.py` | Root legacy research entrypoint | Ambiguous | High | Uses `strategy_families`, `evolution`, `pipeline_artifacts`, and root data path assumptions. |
| `discovery.py` | Root legacy discovery entrypoint | Ambiguous | High | Uses `strategy_families`, root artifact contracts, LanceDB, and direct model wiring. |
| `pipeline_artifacts.py` | Root artifact contract layer for old pipeline | Ambiguous | High | Duplicates artifact role already partly handled by `quant_stack/artifacts/`. |
| `validate_bb_strategy.py` | Strategy-specific validator script | Legacy | High | Direct `engine.*` dependency; explicitly non-canonical. |
| `validate_grid_strategy.py` | Strategy-specific validator script | Legacy | High | Same problem; hardcoded `Data/Binance` assumptions. |
| `live_swarm.py` | Old optimizer/live/research hybrid | Legacy | High | Strong source of agent confusion because it mixes many responsibilities. |
| `execution.py` | Root execution path using old artifacts/families | Legacy | High | Continues old workflow story outside canonical package. |
| `tests/` | Main canonical validation suite | Canonical | Medium | Good structure overall, but still coexists with root `test_*.py`. |
| root `test_*.py` files | Mixed-era tests at repo root | Ambiguous | High | Some validate old systems, some canonical ones; placement teaches agents the wrong conventions. |
| `configs/` | Intended config root | Ambiguous | Low | Currently absent. |
| `docs/` | Main docs root | Canonical | Low | Good place for migration map and workflow docs. |
| `docs/refactor/` | Previous migration docs | Canonical | Medium | Useful evidence, but currently stale relative to the still-live root legacy surface. |
| `docs/research/` | Research-output docs and experiments | Experimental | Medium | Useful history, but not canonical architecture docs. |
| `artifacts/` | Generated local research/experiment outputs | Generated | Low | Should remain local/generated, not source-of-truth architecture. |
| `reports/` | Generated experiment reports | Generated | Low | Same as artifacts; useful outputs, not source code. |
| `data/` | Local canonical-ish working data root | Local data | Medium | Good intended root, but not the only one actually used. |
| `Data/` | Alternate data root used by legacy scripts | Local data | High | Major confusion vector; legacy scripts still assume it. |
| `Binance/`, `Hyperliquid/`, `BTC-Trading-Since-2020/`, `lancedb/` | Local/vendor/generated data roots | Local data | Medium | Should not be treated as canonical package examples. |
| `research/` | Extra root research folder separate from `quant_stack/research/` | Experimental | Medium | Another duplicate naming surface. |
| `scratch/` | Disposable workspace | Experimental | Low | Fine, but should be clearly ignored by agents. |
| `MLEvolve/` | Separate engine/agent framework with many `engine.*` imports | Experimental | High | Strong compatibility hazard if `engine/` moves. |

Bluntly: if agents are copying examples from `engine/`, `strategy_families/`, root `research.py`, `discovery.py`, `live_swarm.py`, root `validate_*.py`, or many files in `scripts/`, the repo is teaching them the wrong workflow.

---

## 3. Target Structure

Baseline target, adapted to the current repo:

```text
quant-factory/
  pyproject.toml
  AGENTS.md
  README.md

  quant_stack/
    backtesting/
    strategies/
    indicators/
    data/
    optimization/
    reporting/
    workflows/
    research/
    intelligence/
    live/
    cli/
    artifacts/

  configs/
  scripts/
  tests/
  docs/
  examples/

  data/
  artifacts/

  legacy/
    engine/
    strategy_families/
    evolution/
    root_entrypoints/
    validation_scripts/
```

### Purpose of each top-level folder

- `quant_stack/` — canonical reusable package and only default extension surface.
- `configs/` — YAML/config presets for workflows, strategies, validation, experiments.
- `scripts/` — thin wrappers only; no heavy business logic.
- `tests/` — all official tests; root `test_*.py` should be folded here over time.
- `docs/` — architecture, workflows, migration rules, research docs.
- `examples/` — query examples, minimal configs, usage examples.
- `data/` — local non-versioned data only.
- `artifacts/` — local generated outputs only.
- `legacy/` — old systems still kept for compatibility/reference, but clearly non-canonical.

### Important adaptation from the current repo

The current repo already has useful `quant_stack/research/`, `quant_stack/intelligence/`, `quant_stack/live/`, and `quant_stack/artifacts/`. Those should remain inside `quant_stack/`; the main cleanup is around **what stays at root** and **what gets pushed under `legacy/`**.

---

## 4. Canonical Workflow

Intended workflow:

strategy idea
→ params model
→ strategy module
→ strategy registry
→ canonical backtester
→ `BacktestResult`
→ standard metrics
→ standard artifacts
→ optimization / CRO / robustness
→ final report

| Workflow step | Current file/class/function | Target file/class/function | Status |
|---|---|---|---|
| Strategy idea | `examples/pipeline_queries/*.yaml`, root `research.py`, root `discovery.py`, `quant_stack/research/strategy_intake/macd_td_v6_intake.py` | `configs/` + `quant_stack/workflows/intake.py` or `quant_stack/research/intake.py` | Split |
| Params model | `quant_stack/strategies/*/params.py` | same | Exists |
| Strategy module | `quant_stack/strategies/*/module.py`, `signals.py`, `spec.py` | same | Exists |
| Strategy registry | `quant_stack/strategies/registry.py` (`StrategyRegistry`, `StrategyModule`) | same | Exists |
| Canonical backtester | `quant_stack/backtesting/polars_engine.py`, optional `vectorbt_engine.py` | `quant_stack/backtesting/` only | Exists |
| Result contract | `quant_stack/backtesting/results.py` (`BacktestResult`) | same | Exists |
| Standard metrics | `quant_stack/backtesting/metrics.py` (`calculate_metrics`) | same | Exists |
| Standard experiment runner | `quant_stack/research/experiments/runner.py` (`run_strategy_experiment`) | `quant_stack/workflows/backtest.py` or canonical wrapper over existing runner | Partial |
| Standard artifacts | `quant_stack/artifacts/store.py`, `quant_stack/research/acceptance_artifacts.py`, root `pipeline_artifacts.py` | `quant_stack/artifacts/` + `quant_stack/reporting/` | Split |
| Optimization / CRO / robustness | `quant_stack/research/optimization/loop.py`, `scripts/run_rsi_momentum_optimization.py`, `scripts/run_rsi_momentum_robustness.py`, `evolution/`, `live_swarm.py` | `quant_stack/optimization/` + thin `scripts/` wrappers | Split |
| Final report | `quant_stack/research/reports.py`, `quant_stack/research/experiments/report.py`, acceptance markdown helpers, ad hoc script reports | `quant_stack/reporting/` | Split |
| Workflow orchestration | `quant_stack/workflows/engine.py`, `quant_stack/research/phase_orchestration/phase19_runner.py`, `scripts/run_pipeline_acceptance.py` | `quant_stack/workflows/` | Partial |

The package has the **core deterministic pieces already**. The main problem is that orchestration, reporting, optimization, and root entrypoints still teach several competing workflows.

---

## 5. What Should Move

This is a planning table only. It is intentionally conservative.

| Source | Destination | Reason | Risk | Required compatibility work |
|---|---|---|---|---|
| `engine/` | `legacy/engine/` | Old strategy-specific backtesting/evaluation system; conflicts with `quant_stack/backtesting/` | High | Keep `engine` import shim or wrapper package until tests, `MLEvolve/`, validators, and root scripts stop importing it |
| `strategy_families/` | `legacy/strategy_families/` | Old strategy abstraction competing with `quant_stack/strategies/` | High | Keep `strategy_families` shim; migrate root `research.py`, `discovery.py`, `execution.py`, tests |
| `evolution/` | `legacy/evolution/` | Old support package still used by root research/artifact flow; not canonical | High | Keep `evolution` shim; update `pipeline_artifacts.py`, root `research.py`, `live_swarm.py`, tests |
| `validate_bb_strategy.py` | `legacy/validation_scripts/validate_bb_strategy.py` | Strategy-specific validation script, non-canonical | Medium | Preserve old wrapper path or script stub; docs/tests may still reference it |
| `validate_grid_strategy.py` | `legacy/validation_scripts/validate_grid_strategy.py` | Same as above | Medium | Same as above |
| root `research.py` | `legacy/root_entrypoints/research.py` | Old root research pipeline bypasses canonical package boundary | High | Thin wrapper or deprecation stub at old path; update README/examples |
| root `discovery.py` | `legacy/root_entrypoints/discovery.py` | Same as above | High | Thin wrapper or deprecation stub; update README/examples |
| `pipeline_artifacts.py` | `quant_stack/artifacts/store.py` or `quant_stack/reporting/legacy_artifacts.py` + root shim | Artifact logic should not live at root | High | Root shim mandatory; many imports still point here |
| `live_swarm.py` | `legacy/root_entrypoints/live_swarm.py` | Large mixed-responsibility legacy orchestration surface | High | Preserve import/CLI wrapper; migrate references carefully |
| `execution.py` | `legacy/root_entrypoints/execution.py` | Legacy execution path using old families/artifacts | High | Wrapper + import audit |
| root `test_*.py` | `tests/legacy/` or proper `tests/` subpackages | Reduce mixed-era examples at root | Medium | Update test commands and import assumptions |
| `quant_stack/research/optimization/` | `quant_stack/optimization/` (eventually) | Matches desired target structure and reduces deep nesting | Medium | Re-export package path; update imports across tests/scripts/docs |
| `quant_stack/research/acceptance_artifacts.py` + `quant_stack/research/experiments/report.py` + `quant_stack/research/reports.py` | `quant_stack/reporting/` | Standardize report/artifact rendering location | Medium | Add compatibility imports, update callers incrementally |
| heavy experiment logic in `scripts/run_rsi_momentum_*.py` | `quant_stack/workflows/` + thin `scripts/` wrappers | `scripts/` should not remain a dumping ground for orchestration logic | Medium | Keep current scripts as wrappers while moving logic gradually |

---

## 6. What Should Not Move Yet

| Path | Why it should stay for now | What depends on it | What must be fixed first |
|---|---|---|---|
| `engine/` | Imports are deeply baked into root scripts, validators, tests, and `MLEvolve/` | `validate_*.py`, `execution.py`, `live_swarm.py`, `test_engine_*`, `MLEvolve/*` | Full import map + wrappers + tested canonical replacements |
| `strategy_families/` | Still active in root `research.py`, `discovery.py`, execution flows, and tests | root research/discovery/execution paths, tests | Replace old family-based flows or maintain stable shim |
| `evolution/` | Still used by root artifact/research surfaces and tests | `pipeline_artifacts.py`, `research.py`, `live_swarm.py`, tests | Decide whether it is truly legacy support only or still operationally required |
| `pipeline_artifacts.py` | Active compatibility surface despite canonical artifact package existing | root research/discovery/execution/tests | Create explicit canonical replacement and keep shim |
| root `research.py` / `discovery.py` | Still documented in README and contain real logic | users, docs, root workflows | README and docs must be redirected first |
| `MLEvolve/` | Imports `engine.*` throughout; moving `engine/` first would break it badly | `MLEvolve/*` | Either isolate MLEvolve as standalone legacy system or migrate its imports deliberately |
| `scripts/run_pipeline_acceptance.py` and `scripts/run_phase19_macd_td_auto.py` | They are near-canonical wrappers already, though they use path hacks | docs, tests, users | Replace `sys.path` hack with robust package entrypoint only after CLI story is unified |

---

## 7. Compatibility Risks

### Likely breakages from moving files

1. **Absolute imports from root packages**
   - `from engine...`
   - `from strategy_families...`
   - `from evolution...`
   - `from pipeline_artifacts...`

2. **Scripts assuming repo-root execution and manual `sys.path` insertion**
   - `scripts/run_pipeline_acceptance.py`
   - `scripts/run_phase19_macd_td_auto.py`
   - related root scripts

3. **Tests importing old modules directly**
   - root `test_engine_*`, `test_strategy_registry.py`, `test_research_guard.py`, `test_live_swarm_experience_logging.py`

4. **Artifacts hardcoded to old paths**
   - `artifacts/latest_validation.json`
   - `artifacts/latest_signal.json`
   - `artifacts/latest_research.json`
   - multiple `artifacts/research/...` assumptions

5. **Data paths hardcoded to non-canonical roots**
   - `Data/Binance/...`
   - some scripts using absolute `/root/quant-factory/data/...`

6. **Config and command assumptions**
   - no `configs/` directory yet
   - no unified console entrypoint in `pyproject.toml`
   - README still points at root research/discovery flows

### Concrete risky imports / dependencies

- `research.py` imports `evolution.*`, `pipeline_artifacts`, and `strategy_families`
- `discovery.py` imports `pipeline_artifacts` and `strategy_families`
- `pipeline_artifacts.py` imports `evolution.schemas`
- `validate_bb_strategy.py` imports `engine.backtester_bb`, `engine.analytics_pro`, `engine.monte_carlo`, `engine.deps`
- `validate_grid_strategy.py` imports `engine.grid_backtester`
- `execution.py` imports `pipeline_artifacts` and `strategy_families`
- `live_swarm.py` imports `engine.*`, `evolution.*`, `pipeline_artifacts`, `strategy_families`
- `MLEvolve/*` imports `engine.*` broadly

### Path risks

- `research.py` hardcodes `Data/Binance/BTC_1m_2025.parquet`
- `engine/deps.py` defaults to `Data/Binance` and `data/quant_factory.duckdb`
- many `scripts/run_rsi_momentum_*.py` assume `Data/Binance`
- `scripts/run_smart_dca_btc.py` and `scripts/run_smart_dca_xauusd.py` hardcode `/root/quant-factory/data/...`

Bottom line: **do not move anything imported as a top-level package without shims**.

---

## 8. Migration Phases

### Phase 0 — No code movement

- **Goal:** clarify ownership and stop agents from learning the wrong paths.
- **Files likely touched:** `README.md`, `AGENTS.md`, `docs/REPO_MAP.md`, `docs/repo_structure_migration_plan.md`, maybe `legacy/README.md` files.
- **Commands to run:**
  - `uv run pytest tests/architecture/test_architecture_boundaries.py -q`
  - targeted import audit commands / grep commands
- **Risk level:** Low
- **Acceptance criteria:**
  - canonical vs legacy vs generated is documented
  - `README.md` and `AGENTS.md` no longer imply root legacy flows are preferred
  - legacy roots are labeled as compatibility/reference only

### Phase 1 — Add canonical wrappers

- **Goal:** expose one official package-first workflow while preserving old entrypoints.
- **Files likely touched:**
  - `quant_stack/workflows/`
  - `quant_stack/cli/`
  - wrappers for root `research.py`, `discovery.py`, `validate_*.py`, `live_swarm.py`
- **Commands to run:**
  - import smoke tests
  - targeted workflow tests in `tests/workflows/`, `tests/research/`, `tests/e2e/`
- **Risk level:** Medium
- **Acceptance criteria:**
  - old commands still work
  - new canonical commands exist
  - no heavy orchestration remains unique to root scripts

### Phase 2 — Deprecate legacy paths

- **Goal:** mark non-canonical systems loudly without moving them yet.
- **Files likely touched:**
  - `engine/*`
  - `strategy_families/*`
  - `evolution/*`
  - root `validate_*.py`, `research.py`, `discovery.py`, `pipeline_artifacts.py`, `live_swarm.py`
- **Commands to run:**
  - import smoke tests for root compatibility modules
  - targeted legacy tests if still retained
- **Risk level:** Low/Medium
- **Acceptance criteria:**
  - every legacy file says it is legacy/reference unless explicitly canonical
  - agents are discouraged from copying these paths
  - compatibility is preserved

### Phase 3 — Move low-risk legacy files

- **Goal:** move the easiest low-value top-level legacy surfaces first.
- **Files likely touched:**
  - `validate_bb_strategy.py`
  - `validate_grid_strategy.py`
  - root `test_*.py` that clearly belong in `tests/legacy/` or canonical `tests/`
- **Commands to run:**
  - targeted tests for moved files
  - documentation link checks / import smoke tests
- **Risk level:** Medium
- **Acceptance criteria:**
  - legacy validation scripts live under `legacy/validation_scripts/`
  - old root paths remain wrapper stubs if needed
  - no test/import regressions from the move

### Phase 4 — Consolidate optimization / CRO

- **Goal:** remove ambiguity around where optimization and CRO live.
- **Files likely touched:**
  - `quant_stack/research/optimization/`
  - target `quant_stack/optimization/`
  - `quant_stack/workflows/`
  - `scripts/run_rsi_momentum_optimization.py`
  - `scripts/run_rsi_momentum_robustness.py`
  - maybe wrappers around `live_swarm.py` concepts
- **Commands to run:**
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/research/optimization/...`
  - canonical import smoke tests
- **Risk level:** Medium/High
- **Acceptance criteria:**
  - one official optimization namespace exists
  - script entrypoints are wrappers only
  - no need to inspect `evolution/` or `live_swarm.py` to discover the optimizer flow

### Phase 5 — Final cleanup

- **Goal:** finish documentation and retire duplicate paths only after proof they are unused.
- **Files likely touched:**
  - `README.md`
  - `AGENTS.md`
  - `docs/`
  - wrappers/shims for old paths
- **Commands to run:**
  - full test suite where possible
  - import smoke tests for supported compatibility paths
- **Risk level:** High
- **Acceptance criteria:**
  - duplicate examples removed from primary docs
  - all canonical commands documented
  - old paths removed only if wrappers/tests prove them unnecessary

---

## 9. Guardrails for Agents

Proposed text to add to `AGENTS.md` later:

### Canonical package rule

`quant_stack/` is the canonical package root. New reusable functionality should be added there unless a task is explicitly about legacy compatibility.

### Thin scripts rule

Root-level and `scripts/` entrypoints must be thin wrappers only. Do not place substantive business logic, backtesting logic, reporting logic, or optimization logic in wrapper scripts.

### Backtester/report standardization rule

Do not create custom strategy-specific backtesters or custom report systems when a canonical `quant_stack` workflow exists. Every public backtest workflow should route through canonical result contracts and standard artifact/report writers.

### Backtest result contract rule

Every public strategy backtest path must return or normalize to `BacktestResult`.

### Legacy-path rule

`engine/`, `strategy_families/`, `evolution/`, root `validate_*.py`, `live_swarm.py`, root `research.py`, and root `discovery.py` are legacy/reference compatibility surfaces unless explicitly marked canonical.

### Optimization/CRO rule

Optimization, CRO, robustness, and candidate comparison should use the canonical workflow, not ad hoc script-local logic.

### Inspect-first rule

When uncertain, inspect canonical workflow files first: strategy registry, canonical backtesting, experiment runner, workflow engine, and artifact/report helpers under `quant_stack/`.

---

## 10. Architecture Tests To Add Later

| Test name | Purpose | Rough implementation idea | Priority |
|---|---|---|---|
| `test_no_new_strategy_specific_backtester_in_quant_stack_backtesting` | Prevent new strategy-specific engines in core | AST/file scan for `run_*_backtest` and strategy-name-specific backtester files under `quant_stack/backtesting/` | High |
| `test_all_public_strategy_runs_normalize_to_backtest_result` | Standardize workflow output | Smoke-run canonical entrypoints and assert returned object/schema is `BacktestResult`-compatible | High |
| `test_no_imports_from_legacy_inside_quant_stack` | Prevent future leakage from legacy back into canonical package | Scan imports under `quant_stack/` for `legacy`, `engine`, `strategy_families`, `evolution` | High |
| `test_scripts_are_thin_wrappers` | Stop `scripts/` from becoming orchestration dumping grounds | Set simple thresholds / structural rules: wrapper should call `quant_stack.*` entrypoint and avoid large inline logic blocks | High |
| `test_registered_strategies_run_through_standard_workflow` | Ensure registry and backtester integrate consistently | Iterate over `available_strategies()` with small synthetic fixture and assert canonical workflow path runs | Medium |
| `test_reporting_uses_standard_artifact_writer` | Prevent ad hoc report systems | Search report modules/scripts for writes outside approved artifact/report helpers | Medium |
| `test_single_canonical_optimization_entrypoint_exists` | Enforce one official optimization surface | Assert that canonical optimization namespace is present and scripts call it | Medium |
| `test_root_test_files_are_empty_or_wrapper_only` | Reduce mixed-era examples at root | Fail if new root `test_*.py` files are added outside approved compatibility exceptions | Medium |

---

## 11. Recommended Canonical Commands

### Near-term commands based on what already exists

These are the closest current canonical commands:

```bash
uv run python -m quant_stack.cli.run_backtest \
  --data-path /root/quant-factory/data/XAUUSD.parquet \
  --strategy rsi_sma \
  --params-json '{}'

uv run python -m quant_stack.cli.run_strategy_experiment \
  --strategy funding_exhaustion_reversal \
  --dataset data/features/bybit/BTCUSDT/1m/features.parquet \
  --symbol BTCUSDT \
  --timeframe 1m \
  --start 2024-01-01T00:00:00+00:00 \
  --end 2024-03-01T00:00:00+00:00 \
  --output-dir artifacts/research/experiments

uv run python scripts/run_pipeline_acceptance.py \
  --query examples/pipeline_queries/btc_rsi_sma_context_filter.yaml \
  --output-dir artifacts/test_acceptance_run
```

### Future canonical commands to converge on

```bash
uv run python -m quant_stack.cli backtest \
  --strategy smart_dca \
  --data /root/quant-factory/data/XAUUSD.parquet \
  --config configs/smart_dca/xauusd.yaml

uv run python -m quant_stack.cli optimize \
  --strategy smart_dca \
  --data /root/quant-factory/data/XAUUSD.parquet \
  --config configs/smart_dca/xauusd.yaml

uv run python -m quant_stack.cli validate \
  --strategy smart_dca \
  --data /root/quant-factory/data/XAUUSD.parquet \
  --config configs/smart_dca/xauusd.yaml

uv run python -m quant_stack.cli report \
  --artifact artifacts/research/experiments/latest.json
```

### What these future commands imply

- `quant_stack/cli/__init__.py` or a unified `quant_stack/cli.py` should expose one official command surface.
- `configs/` should become real, not hypothetical.
- old script names can remain as thin wrappers calling the canonical CLI.

---

## Final Recommendation

Do **not** start by moving `engine/` or `strategy_families/` physically.

Start by making the repo **tell the truth**:

1. document `quant_stack/` as the only default extension surface,
2. mark root legacy systems as compatibility/reference only,
3. make scripts thin wrappers over canonical package entrypoints,
4. add architecture tests that enforce the target structure,
5. only then begin moving low-risk legacy files.

The biggest current problem is not the absence of a target architecture. The repo already has one. The problem is that the old and new systems are both still visible enough that agents cannot tell which one they are supposed to copy.
