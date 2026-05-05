# Phase 17 — End-to-End Pipeline Acceptance Harness

## TL;DR
> **Summary**: Build a deterministic smoke harness that proves the current stack composes safely from OHLCV input through strategy signals and Polars backtesting, with intelligence context attached via backward as-of semantics and an optional proposed-only optimization request artifact.
> **Deliverables**:
> - `examples/pipeline_queries/btc_rsi_sma_context_filter.yaml`
> - `examples/pipeline_queries/btc_bb_breakout_context_filter.yaml`
> - `scripts/run_pipeline_acceptance.py`
> - `tests/e2e/test_pipeline_acceptance.py`
> - `docs/PIPELINE_ACCEPTANCE.md`
> - JSON + markdown acceptance artifacts written by the harness
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: Query schema + deterministic fixtures → orchestration harness → e2e assertions → artifacts/docs

## Context
### Original Request
Execute Phase 17 only: create a deterministic end-to-end smoke pipeline proving `data → indicators → strategy signals → backtest → intelligence context join → validation → optional optimization request artifact`, without touching strategy logic, optimizer internals, live trading, broker/execution/risk modules, or requiring real credentials.

### Interview Summary
- No clarification round was needed because the request is fully scoped.
- Existing repo surfaces already cover OHLCV validation, strategy signal builders, Polars backtesting, intelligence event normalization/storage/join, workflow queueing, and optimization request models.
- The critical design decision is that context must be joined onto a timestamped bar-level frame, not `BacktestResult.trades`, because `trades` is a `list[float]` only.
- `grid` is excluded because it is path-dependent and not appropriate for this smoke proof.

### Metis Review (gaps addressed)
- Fixed the underspecified “baseline vs candidate” delta: candidate applies a post-strategy context gate only; strategy logic itself does not change.
- Fixed the optional optimization artifact ambiguity: create both typed JSON artifact and proposed queue record only, with no worker execution.
- Added guardrails for symbol consistency, no-event edge cases, `historical_integrity=False`, same-timestamp joins, and null context before first eligible event.
- Added explicit repeatability and no-future-leakage acceptance criteria at the composed pipeline level.

## Work Objectives
### Core Objective
Produce a deterministic acceptance harness that exercises the existing stack end-to-end for two signal-stream strategies (`rsi_sma`, `bb_breakout`) and proves the composed pipeline respects no-lookahead and no-future-leakage semantics while emitting reusable artifacts.

### Deliverables
- Two YAML pipeline query examples for BTC using `rsi_sma` and `bb_breakout`.
- A script entrypoint that loads a query, generates/loads deterministic OHLCV + mock intelligence signals, runs baseline and context-filtered paths, validates outputs, and writes JSON + markdown artifacts.
- A single end-to-end test module covering parsing, deterministic fixtures, baseline/candidate backtests, context join safety, artifact writing, and proposed-only optimization request behavior.
- A human-readable doc describing how to run the harness and interpret artifacts.

### Definition of Done (verifiable conditions with commands)
- `uv run python scripts/run_pipeline_acceptance.py --query examples/pipeline_queries/btc_rsi_sma_context_filter.yaml --output-dir /tmp/pipeline-acceptance-rsi`
- `uv run python scripts/run_pipeline_acceptance.py --query examples/pipeline_queries/btc_bb_breakout_context_filter.yaml --output-dir /tmp/pipeline-acceptance-bb`
- `uv run python -m unittest tests.e2e.test_pipeline_acceptance`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/e2e/test_pipeline_acceptance.py`
- `uv run python -m compileall -q -x '(^|/)(\.venv|\.git|Data|data|__pycache__)(/|$)' .`

### Must Have
- Deterministic OHLCV fixture or local fixture generation only.
- Deterministic mock intelligence events persisted through `quant_stack.intelligence.store`.
- Bar-level or derived-event context attachment using backward-only as-of semantics.
- Baseline and candidate runs using identical strategy, params, OHLCV, and backtest engine.
- Candidate differs only by a context-derived gating/filter layer on the existing signal stream.
- JSON artifact, markdown report, joined context frame artifact, and optional proposed-only optimization request artifact.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No new strategy formulas.
- No optimizer execution, worker execution, or auto-approved optimization request.
- No live trading, broker imports, execution imports, account access, or risk-limit mutation.
- No `pandas` usage in the core harness path.
- No use of `grid` strategy.
- No joins against `BacktestResult.trades`.
- No forward context fill from future timestamps.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after + existing `unittest` and `pytest`
- QA policy: Every task includes agent-executed scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
Wave 1: query schema/examples + deterministic fixtures + context/join harness contracts + artifact/report schema
Wave 2: script orchestration + e2e tests + docs

### Dependency Matrix (full, all tasks)
- 1 blocks 5, 6
- 2 blocks 5, 6
- 3 blocks 5, 6
- 4 blocks 5, 6
- 5 blocks 6
- 6 blocks Final Verification Wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 4 tasks → quick / unspecified-low
- Wave 2 → 2 tasks → unspecified-high / writing
- Final Verification → 4 tasks → oracle / unspecified-high / deep

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Define the acceptance query contract and checked-in YAML examples

  **What to do**: Create a small typed query schema inside the new acceptance harness path that captures strategy name, BTC symbol, timeframe, fixture mode, context-gating thresholds, validation expectations, artifact output preferences, and optional optimization artifact toggle. Use it to author exactly two YAML files: `btc_rsi_sma_context_filter.yaml` and `btc_bb_breakout_context_filter.yaml`. Normalize symbol/timeframe values to the repo’s canonical expectations and explicitly reject `grid`.
  **Must NOT do**: Do not introduce a general config system, remote config loading, or support arbitrary strategies in Phase 17.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: isolated schema + example file work.
  - Skills: `[]` - Reason: existing repo patterns are sufficient.
  - Omitted: `['playwright']` - Reason: no browser interaction.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6 | Blocked By: none

  **References**:
  - Pattern: `quant_stack/research/optimization/schemas.py` - typed request schema style.
  - Pattern: `quant_stack/workflows/schemas.py` - event/workflow typed config style.
  - Pattern: `README.md` - repo CLI/example documentation style.

  **Acceptance Criteria**:
  - [ ] YAML queries parse into a typed model without custom runtime prompts.
  - [ ] The model rejects unsupported strategy names and caps `max_iterations` if optimization artifact emission is enabled.
  - [ ] The examples are deterministic and BTC-only for this phase.

  **QA Scenarios**:
  ```
  Scenario: Parse both checked-in YAML queries
    Tool: Bash
    Steps: Run a small Python command importing the acceptance query loader against both YAML files.
    Expected: Both files parse successfully into the typed query model.
    Evidence: .sisyphus/evidence/task-1-query-parse.txt

  Scenario: Reject unsupported grid strategy
    Tool: Bash
    Steps: Feed a temporary YAML with `strategy_name: grid` into the query loader.
    Expected: Loader exits with a clear validation error mentioning `grid` is out of scope.
    Evidence: .sisyphus/evidence/task-1-query-reject.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `examples/pipeline_queries/*`

- [x] 2. Build deterministic OHLCV and intelligence fixture generation for the harness

  **What to do**: Implement deterministic sample BTC OHLCV generation or local fixture loading that flows through `validate_ohlcv()`. Implement deterministic mock intelligence `SignalEvent` creation for funding, basis, depth imbalance, and liquidation imbalance, persisted through `save_events()` under a temporary/root output path. Ensure some early bars have no eligible context and at least one signal uses `historical_integrity=False` to exercise exclusion semantics.
  **Must NOT do**: Do not call external APIs, OKX endpoints, or credentialed services.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: fixture generation and persistence using existing helpers.
  - Skills: `[]` - Reason: no special workflow needed.
  - Omitted: `['git-master']` - Reason: no git work required.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6 | Blocked By: none

  **References**:
  - Pattern: `quant_stack/research/tools.py::_synthetic_ohlcv` - deterministic OHLCV style.
  - Pattern: `quant_stack/data/validation.py::validate_ohlcv` - canonical OHLCV contract.
  - Pattern: `quant_stack/intelligence/normalize.py::*_to_signal_events` - event conversion shape.
  - Pattern: `quant_stack/intelligence/store.py::save_events` - event persistence layout.
  - Test: `tests/intelligence/test_snapshot.py` - historical integrity and no-future leakage cases.

  **Acceptance Criteria**:
  - [ ] Fixture OHLCV passes `validate_ohlcv()`.
  - [ ] Fixture events serialize and reload through the intelligence store.
  - [ ] The fixture set includes missing-context early bars and excluded historical-integrity-false events.

  **QA Scenarios**:
  ```
  Scenario: Deterministic fixture generation round-trip
    Tool: Bash
    Steps: Run the fixture generator twice and compare normalized OHLCV + event artifacts.
    Expected: Outputs are field-stable across runs.
    Evidence: .sisyphus/evidence/task-2-fixtures.txt

  Scenario: Historical-integrity-false event excluded from history usage
    Tool: Bash
    Steps: Build snapshot after persisting one excluded liquidation event and inspect snapshot fields.
    Expected: Excluded event does not populate the historical snapshot field.
    Evidence: .sisyphus/evidence/task-2-historical-integrity.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `scripts/run_pipeline_acceptance.py`, harness helper modules if created under script scope

- [x] 3. Define the context-gating contract on top of existing strategy signals

  **What to do**: Specify and implement the candidate transformation as a pure post-strategy gating step applied after `build_signals()` and before `PolarsSignalBacktester.run()`. Baseline uses raw strategy signals; candidate uses the same signals but zeroes or suppresses entries when query-defined context filters fail (for example max spread, required depth imbalance range, or banned missing-context behavior). This must operate on the timestamped signal/bar frame, not the strategy module itself.
  **Must NOT do**: Do not alter strategy formulas, parameters, or indicator logic.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: small orchestration contract, but correctness-sensitive.
  - Skills: `[]`
  - Omitted: `['refactor']` - Reason: no architectural rewrite needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6 | Blocked By: none

  **References**:
  - Pattern: `quant_stack/strategies/rsi_sma/signals.py::build_signals`
  - Pattern: `quant_stack/strategies/bb_breakout/signals.py::build_signals`
  - Pattern: `quant_stack/intelligence/regime_context.py::optimizer_context_filter` - filter-style context gating.
  - Pattern: `quant_stack/intelligence/snapshot.py::build_context_frame` - context frame shape.

  **Acceptance Criteria**:
  - [ ] Baseline and candidate share identical OHLCV, params, and raw strategy outputs before gating.
  - [ ] Candidate differs only by deterministic context gating columns/logic.
  - [ ] No strategy source files are modified.

  **QA Scenarios**:
  ```
  Scenario: Baseline and candidate share same raw strategy signal frame
    Tool: Bash
    Steps: Serialize the pre-gating signal frame for both baseline and candidate code paths.
    Expected: Pre-gating signal values are identical.
    Evidence: .sisyphus/evidence/task-3-pre-gating.txt

  Scenario: Context gate suppresses entries when spread threshold fails
    Tool: Bash
    Steps: Use a fixture with one high-spread interval and inspect candidate signal output.
    Expected: Candidate suppresses entries only in intervals failing the configured threshold.
    Evidence: .sisyphus/evidence/task-3-gating.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `scripts/run_pipeline_acceptance.py`

- [x] 4. Define deterministic artifact and report outputs

  **What to do**: Decide and implement a stable artifact layout under the acceptance output directory: raw query echo, validated OHLCV snapshot, persisted intelligence event frame, joined context frame, baseline backtest summary, candidate backtest summary, validation result, optional proposed optimization request artifact, and markdown report. Use typed JSON artifacts wherever possible and deterministic field ordering/content.
  **Must NOT do**: Do not introduce a new global artifact subsystem; reuse existing JSON/markdown patterns.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: artifact/report structure plus human-readable markdown.
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']` - Reason: not UI work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6 | Blocked By: none

  **References**:
  - Pattern: `quant_stack/artifacts/store.py::save_artifact`
  - Pattern: `quant_stack/research/reports.py::render_research_report`
  - Pattern: `pipeline_artifacts.py` - legacy JSON artifact naming ideas.

  **Acceptance Criteria**:
  - [ ] Harness writes deterministic JSON artifacts and one markdown report.
  - [ ] Optional optimization request artifact is proposed-only and includes `created_by="workflow"`-style provenance equivalent for the harness path if used.
  - [ ] Artifact paths are documented in `PIPELINE_ACCEPTANCE.md`.

  **QA Scenarios**:
  ```
  Scenario: Artifact set written for one pipeline run
    Tool: Bash
    Steps: Run acceptance script once and list output directory contents.
    Expected: JSON artifacts and markdown report exist with expected names.
    Evidence: .sisyphus/evidence/task-4-artifacts.txt

  Scenario: Optional optimization artifact remains proposed
    Tool: Bash
    Steps: Enable optional optimization artifact creation and inspect stored request/queue record.
    Expected: Request is created but not approved and no worker execution occurs.
    Evidence: .sisyphus/evidence/task-4-opt-request.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `docs/PIPELINE_ACCEPTANCE.md`, script artifact helpers

- [x] 5. Implement the orchestrating acceptance script and YAML-driven execution path

  **What to do**: Build `scripts/run_pipeline_acceptance.py` to load a query YAML, generate/load fixtures, run `validate_ohlcv()`, acquire the strategy via `get_strategy()`, build features/signals, derive baseline and candidate signal frames, run `PolarsSignalBacktester`, build/load the intelligence context frame, attach context with backward-only semantics, run `validate_metrics()` on both runs, compare outcomes, optionally create a proposed optimization request artifact, and write the report/artifacts. The script must default to no optimizer execution.
  **Must NOT do**: Do not call optimizer loop, worker, live modules, broker modules, or external APIs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: main orchestration path across many existing modules.
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 6 | Blocked By: 1, 2, 3, 4

  **References**:
  - Pattern: `quant_stack/research/tools.py::request_backtest_from_plan` - safe orchestration style.
  - Pattern: `quant_stack/cli/run_backtest.py` - script/CLI entrypoint style.
  - API/Type: `quant_stack/strategies/registry.py::get_strategy`
  - API/Type: `quant_stack/backtesting/polars_engine.py::PolarsSignalBacktester.run`
  - API/Type: `quant_stack/intelligence/snapshot.py::build_context_frame`, `join_context_to_trades`
  - API/Type: `quant_stack/research/optimization/schemas.py::OptimizationRequest`

  **Acceptance Criteria**:
  - [ ] Running each YAML query completes without credentials.
  - [ ] Baseline and candidate backtests both run deterministically.
  - [ ] Candidate context join uses only `timestamp <= target timestamp` data.
  - [ ] Optional optimization request artifact is created in proposed state only.

  **QA Scenarios**:
  ```
  Scenario: RSI acceptance run completes end-to-end
    Tool: Bash
    Steps: Execute the script with `btc_rsi_sma_context_filter.yaml` and an empty output dir.
    Expected: Script exits 0 and writes artifact/report set.
    Evidence: .sisyphus/evidence/task-5-rsi-run.txt

  Scenario: BB acceptance run completes end-to-end
    Tool: Bash
    Steps: Execute the script with `btc_bb_breakout_context_filter.yaml` and an empty output dir.
    Expected: Script exits 0 and writes artifact/report set.
    Evidence: .sisyphus/evidence/task-5-bb-run.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `scripts/run_pipeline_acceptance.py`

- [x] 6. Add the composed end-to-end acceptance test and user-facing documentation

  **What to do**: Implement `tests/e2e/test_pipeline_acceptance.py` and `docs/PIPELINE_ACCEPTANCE.md`. The test must assert: query parse success, validated sample data, baseline backtest, context-filtered backtest, preserved no-lookahead execution, no future context leakage, artifact creation, and proposed-only optimization request behavior. The doc must explain the deterministic fixture philosophy, strategy scope, artifact outputs, and exactly how to run both example queries.
  **Must NOT do**: Do not write docs implying live data or optimizer execution occurs.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: docs + explicit test narrative, but with some code work.
  - Skills: `[]`
  - Omitted: `['caveman-review']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final Verification Wave | Blocked By: 1, 2, 3, 4, 5

  **References**:
  - Test: `tests/intelligence/test_snapshot.py` - no-future-leakage assertions.
  - Test: `test_quant_stack_backtesting_live_research_cli.py` - no-lookahead backtest assertion style.
  - Test: `tests/workflows/test_actions.py`, `tests/workflows/test_engine.py` - proposed queue request expectations.
  - Doc Pattern: `README.md` - concise run-command documentation style.

  **Acceptance Criteria**:
  - [ ] All requested e2e assertions exist in one test module.
  - [ ] Docs show both example commands and artifact interpretation.
  - [ ] Tests run without OKX credentials or live/broker dependencies.

  **QA Scenarios**:
  ```
  Scenario: E2E suite passes under unittest
    Tool: Bash
    Steps: Run `uv run python -m unittest tests.e2e.test_pipeline_acceptance`.
    Expected: All e2e tests pass.
    Evidence: .sisyphus/evidence/task-6-unittest.txt

  Scenario: E2E suite passes under pytest
    Tool: Bash
    Steps: Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests/e2e/test_pipeline_acceptance.py`.
    Expected: All e2e tests pass.
    Evidence: .sisyphus/evidence/task-6-pytest.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `tests/e2e/test_pipeline_acceptance.py`, `docs/PIPELINE_ACCEPTANCE.md`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Single commit after all Phase 17 files and tests are green.
- Suggested message: `add pipeline acceptance harness`

## Success Criteria
- Both YAML examples run end-to-end with deterministic fixtures.
- Baseline and candidate backtests are reproducible and differ only by context gating.
- The harness proves no-lookahead and no-future-leakage semantics at the composed pipeline level.
- Optional optimization request artifact is proposed-only and never executed.
- No live/broker/risk modules are touched.
