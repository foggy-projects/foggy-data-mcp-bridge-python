# P0 Python Alignment Upgrade Plan

Date: 2026-06-06

Scope: Python engine capability alignment against the current Java 3.x / 9.x
engine line. Productization and Odoo business model expansion are explicitly out
of scope for the first phase unless needed as read-only fixtures.

## Repository State

Checked before this audit. Existing changes were not reverted, cleaned,
committed, or pushed.

| Repo | Branch/status summary |
| --- | --- |
| Java mainline `foggy-data-mcp-bridge-wt-dev-compose` | `main...origin/main`, with existing modified Odoo templates, docs, demo SQL/data, Java test resources, scripts, and many untracked Odoo/domain skill/model/fixture files. Left untouched. |
| Python `foggy-data-mcp-bridge-python` | `v3.0/engine-skill-next...origin/v3.0/engine-skill-next`, with existing modified `dict_def.py`, loader `__init__.py`, `semantic/service.py`, and untracked `tests/test_dataset_model/test_dictionary_discovery_metadata.py`. Left untouched. |
| Model registry `foggy-model-registry` | `main...origin/main`, clean at final status check. Left untouched. |

This document lives under `docs/v3.8-python-alignment` to keep the Python
alignment iteration isolated from both the older Python `v1.x` docs and any
future Python `v3.0` mainline docs. The active Python branch is already
`v3.0/engine-skill-next`, while the Java alignment targets include
`docs/v3.0` plus 9.x engine docs.

## Documents Reviewed

Python:

- `CLAUDE.md`, `README.md`, `pyproject.toml`
- `docs/8.2.0.beta/README.md`
- `docs/8.2.0.beta/P0-ComposeQuery-QueryPlan派生查询与关系复用规范-progress.md`
- `docs/v1.15/README.md`
- `docs/v1.15/acceptance/java-python-engine-parity-baseline.md`
- `docs/v1.15/coverage/java-python-test-parity-coverage-audit.md`
- `docs/v1.16/BUG-compose-derived-plan-having-contract-gap.md`
- `src/`, `tests/`, and `scripts/` structure

Java:

- `docs/dev-guide/compose-query.md`
- `docs/9.0.0.beta/README.md`
- `docs/9.0.0.beta/detailed_design/00-*.md`
- `docs/9.0.0.beta/detailed_design/01-*.md`
- `docs/9.0.0.beta/detailed_design/02-*.md`
- `docs/9.0.0.beta/detailed_design/04-*.md`
- `docs/9.0.0.beta/detailed_design/07-*.md`
- `docs/9.1.0/README.md`
- `docs/9.1.0/detailed_design/10-*.md`
- `docs/9.1.0/detailed_design/13-*.md`
- `docs/9.1.0/domain_models/*`
- `docs/9.1.0/workitems/P1-odoo-model-registry-promotion-20260606.md`
- `docs/9.1.0/workitems/P2-ai-llm-report-tool-business-error-observability-20260604.md`
- `docs/9.2.0/README.md`
- `docs/9.2.0/workitems/query-model-aggregate-join.md`
- `docs/9.2.0/acceptance/query-model-aggregate-join-acceptance.md`
- `docs/v3.0/README.md`
- `docs/v3.0/workitems/REQ-compose-join-qualified-field-references-java-parity.md`
- `docs/v3.0/workitems/REQ-compose-source-alias-lexical-scope-and-ambiguity.md`

Registry:

- Git status only in this round. Registry contents were not edited.

## Current Python Baseline

Scope clarification:

- This P0 line is the Python engine to Java engine alignment line.
- Work should stay on engine-neutral fixtures, fail-closed boundaries,
  compiler/runtime contracts, SQL shape, metadata, governance, diagnostics, and
  live-result parity.
- Productization, Odoo business model expansion, generated registry refreshes,
  UI behavior, and AI orchestration are not part of this P0 line unless a
  separate approved work item explicitly expands scope.

Static baseline:

- Runtime requirement: Python 3.11+.
- `pyproject.toml` package version remains `0.1.0`.
- README historical baseline says `1322 passed, 76 skipped`, but versioned docs
  show later engine baselines:
  - v1.15 accepted baseline: `3977 passed`.
  - v1.16 progress note: `4100 passed, 4 failed`, with failures recorded
    outside the compose same-stage-alias fix path.

Current command results:

| Command | Result |
| --- | --- |
| `python -m pytest --tb=short -q` | Failed before collection: `python` not found in this shell. |
| `python3 -m pytest --tb=short -q` | Failed before collection: system Python 3.12 has no `pytest`. |
| `.venv/bin/python -m pytest --tb=short -q` | Initial baseline: `4048 passed, 159 skipped, 7 failed, 43 warnings in 18.27s`. |
| `.venv/bin/python -m pytest --tb=short -q -rs` | After P0-1 baseline repair: `4095 passed, 162 skipped, 43 warnings in 17.44s`. |

Initial failures:

| Area | Failing tests | Observed reason |
| --- | --- | --- |
| Formula Java snapshot catalog | `tests/integration/test_formula_parity.py::{test_catalog_has_coverage_targets,test_committed_snapshot_not_hand_edited,test_parity_matches_java_snapshot}` | Catalog/snapshot drift: catalog has 0 comparable cases, while committed snapshot still contains formula case ids such as `ari-*`, `cmp-*`, `bool-*`, `agg-*`, `ar-*`. |
| PostgreSQL conditional aggregate real DB | Four parameterized cases in `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py::TestConditionalAggregateIfRealDbAlignment::test_postgres_alignment_against_native_sql` | Local Postgres fixture is unavailable at `localhost:15432`; connection refused on `::1` and `127.0.0.1`. |

P0-1 follow-up:

- `BUG-P0-1A` fixed formula catalog resolution for the current Java worktree.
- `BUG-P0-1B` added external DB profile probes for conditional aggregate IF.
- Current local full baseline passes with optional unavailable DB/resource lanes
  skipped.

P0-2 follow-up:

- Added `tests/fixtures/java_snapshot_parity_manifest.json` as the active and
  planned Java snapshot lane manifest.
- Added `tests/integration/test_java_snapshot_parity_manifest.py` as the
  always-on manifest gate.
- Active lanes currently cover formula and timeWindow. Planned lanes reserve
  compose query, script runtime tool, pivot/domain transport, governance, and
  neutral domain fixture runner exports.
- Focused active-lane check passed:
  `74 passed in 0.54s`.

P0-3 follow-up:

- Added optional compose replay harness at
  `tests/integration/test_java_compose_snapshot_parity.py`.
- Added Java snapshot producer in the Java worktree:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/compilation/JavaComposeSnapshotTest.java`.
- Generated fixture:
  `tests/fixtures/java_compose_snapshot_parity.json`.
- Compose manifest lane is now active and points to the fixture plus replay
  test.
- Snapshot currently covers base, derived filter/order/limit, union all,
  qualified source-alias join, source-alias projection/slice/orderBy after
  join, inherited source-alias refs through derived query, dropped-column
  source alias refusal, and SQL Server fallback forbidden `FROM (WITH` shape.
- Focused Java producer passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`.
- Focused Python replay passed:
  `2 passed in 0.46s`.
- Manifest + compose replay after lane activation passed:
  `6 passed in 0.45s`.
- Current full baseline after activating the compose snapshot fixture:
  `4101 passed, 162 skipped, 43 warnings in 17.85s`.

P0-4 follow-up:

- Added Java snapshot producer in the Java worktree:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/runtime/JavaComposeScriptSnapshotTest.java`.
- Generated fixture:
  `tests/fixtures/java_compose_script_snapshot_parity.json`.
- Added Python replay harness:
  `tests/integration/test_java_compose_script_snapshot_parity.py`.
- Compose script manifest lane is now active and validates MCP resource markers,
  Java runtime global surface, literal return, empty plans envelope,
  preview-mode SQL capture, and security-parameter fail-closed behavior.
- Java producer passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeScriptSnapshotTest`.
- Focused Python replay passed:
  `4 passed in 0.41s`.
- Manifest + P0-4 replay passed:
  `8 passed in 0.41s`.
- Current full baseline after activating the compose script snapshot fixture:
  first run had one intermittent `test_suspend_limits.py` cleanup failure; the
  failing test and file passed directly, and the second full run passed with
  `4105 passed, 162 skipped, 43 warnings in 17.36s`.
- Known remaining script/runtime gap: decide whether Python's extra fsscript
  global surface should remain an accepted divergence. Header bridge payloads
  are covered by P0-26, capability allow/deny snapshots are covered by P0-27,
  generic resolver factory exception payloads are covered by P0-34, and
  resolver `resolve(...)` upstream-failure payloads are covered by P0-40.
  Legacy Java `DataSetResult` / `ComposedDataSetResult` methods are now treated
  as outside the current `dataset.compose_script` SemanticDSL surface unless
  product explicitly reopens that API.

P0-5 follow-up:

- Added Java snapshot producer in the Java worktree:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/security/JavaGovernanceSnapshotTest.java`.
- Generated fixture:
  `tests/fixtures/java_governance_snapshot_parity.json`.
- Added Python replay harness:
  `tests/integration/test_java_governance_snapshot_parity.py`.
- Governance manifest lane is now active and validates `fieldAccess` null vs
  empty-list semantics, per-base governance forwarding, and missing
  visible-model binding fail-closed compile errors.
- Java producer passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`.
- Manifest + P0-5 replay passed:
  `6 passed in 0.44s`.
- Current full baseline after activating the governance snapshot fixture:
  `4107 passed, 162 skipped, 43 warnings in 17.48s`.
- Remaining governance gaps after P0-5: queryModel denied-column SQL refusal,
  metadata visible-model trimming, cross-model calculated-field refusals, and
  sanitized error payload snapshots.

P0-6 follow-up:

- Extended the active governance snapshot producer/replay instead of creating a
  parallel fixture:
  `JavaGovernanceSnapshotTest.java`,
  `tests/fixtures/java_governance_snapshot_parity.json`, and
  `tests/integration/test_java_governance_snapshot_parity.py`.
- Added neutral Java cases for denied physical-column to QM-field mapping,
  query validation refusals for `columns` and `orderBy`, unrelated physical
  column pass-through, metadata `deniedColumns` trimming, and
  `visibleFields - deniedColumns` trimming.
- Python replay now uses the real `SemanticQueryService` plus demo
  `FactSalesModel` to validate mapping, query validation, and
  `get_metadata_v3` behavior.
- Manifest `permission-visible-model-snapshots` now advertises these P0-6
  contracts as active coverage.
- Focused Java producer passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`.
- Focused Python replay plus manifest passed:
  `6 passed in 0.44s`.
- Remaining governance gaps: visible model allow/deny cases from authority
  resolution, cross-model calculated-field refusals, sanitized error payloads,
  pivot/domain governance propagation, and aggregate-join governance
  propagation. P0-16 later closes the pivot/domain propagation snapshot gap.

P0-7 follow-up:

- Added Java snapshot producer in the Java worktree:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/pivot/JavaPivotDomainSnapshotTest.java`.
- Generated fixture:
  `tests/fixtures/java_pivot_domain_snapshot_parity.json`.
- Added Python replay harness:
  `tests/integration/test_java_pivot_domain_snapshot_parity.py`.
- Pivot/domain manifest lane is now active and validates Pivot DTO parsing,
  ordinary flat pivot translation, SQLite/Postgres/MySQL8 domain renderer
  fragments, params, NULL-safe join predicates, and empty-column fail-closed
  behavior.
- The lane records a concrete gap: Java supports MySQL 5.7 domain transport via
  `DERIVED_TABLE`; Python currently refuses `mysql5.x` domain transport.
- Focused Java producer passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaPivotDomainSnapshotTest`.
- Focused Python replay plus manifest passed:
  `6 passed in 0.41s`.
- Ruff passed for the new Python replay.
- First full pytest run hit an intermittent compose pause/resume failure in
  `tests/compose/runtime/test_handler_pause.py::TestFailClosed::test_resume_after_reject`;
  the same test passed directly, and the second full run passed with
  `4109 passed, 162 skipped, 43 warnings in 17.59s`.
- Remaining pivot/domain gaps after P0-7: real flat/grid result snapshots,
  subtotal and grand-total output snapshots, non-additive auxiliary requery
  snapshots, `baselineRatio` output snapshots, large-domain threshold/limit
  refusal snapshots, and pivot/domain governance propagation.

P0-8 follow-up:

- Added Java snapshot producer in the Java worktree:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/pivot/JavaPivotOutputSnapshotTest.java`.
- Generated fixture:
  `tests/fixtures/java_pivot_output_snapshot_parity.json`.
- Added Python replay harness:
  `tests/integration/test_java_pivot_output_snapshot_parity.py`.
- Pivot output manifest lane is now active and validates real SQLite flat
  rows, flat rows+columns, and grid rows+columns output over an isolated
  neutral seed.
- The lane recorded a concrete Python gap: same-service flat/grid Pivot
  requests with the same translated axes and metrics could collide in cache
  before output shaping. BUG-P0-9 now covers the regression and fix.
- Default focused Java command with the `multi-db` profile failed because local
  Postgres was unavailable at `localhost:15432`.
- Focused Java producer passed with SQLite-focused execution:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`.
- Focused Python replay passed:
  `2 passed in 0.42s`.
- Remaining Pivot output gaps: subtotal and grand-total output snapshots,
  `parentShare` output snapshots, non-additive auxiliary requery snapshots,
  `baselineRatio` output snapshots, large-domain threshold/limit refusal
  snapshots, and pivot/domain governance propagation.

P0-9 follow-up:

- Added BUG workitem:
  `docs/v3.8-python-alignment/workitems/BUG-P0-9-pivot-output-cache-key-collision.md`.
- Updated P0-8 Python replay so flat/grid output snapshot cases execute against
  one cached `SemanticQueryService` instance.
- Confirmed the pre-fix failure: the grid case received flat rows+columns from
  cache.
- Fixed Python query cache isolation by adding the original Pivot request shape
  to the execute cache key before Pivot translation.
- Focused replay, P0-7/P0-8/manifest plus existing Pivot grid tests passed.
- Ruff passed for touched replay/manifest tests; full `service.py` ruff remains
  blocked by existing broad modernization findings and was not auto-fixed.
- Full pytest was attempted and hit the known intermittent compose suspend
  cleanup area; the failed test passed when rerun directly.

P0-10 follow-up:

- Extended the active P0-8 Pivot output snapshot producer/replay instead of
  creating a parallel fixture:
  `JavaPivotOutputSnapshotTest.java`,
  `tests/fixtures/java_pivot_output_snapshot_parity.json`, and
  `tests/integration/test_java_pivot_output_snapshot_parity.py`.
- Added Java grandTotal output cases for flat rows, flat rows+columns, and grid
  rows+columns over the same isolated neutral SQLite seed.
- Aligned Python grandTotal row-axis marker with Java: row subtotals continue
  to use `ALL`, while grandTotal rows use `GRAND_TOTAL` and carry
  `_sys_meta.isGrandTotal=true`.
- Focused Java exporter passed with SQLite-focused execution:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`.
- Focused Python replay and affected grandTotal helper tests passed:
  `6 passed in 0.48s`.
- Remaining Pivot output gaps after P0-10: row subtotal output snapshots,
  `parentShare` output snapshots, non-additive auxiliary requery snapshots,
  `baselineRatio` output snapshots, large-domain threshold/limit refusal
  snapshots, and pivot/domain governance propagation.

P0-11 follow-up:

- Extended the active P0-8/P0-10 Pivot output snapshot producer/replay instead
  of creating a parallel fixture:
  `JavaPivotOutputSnapshotTest.java`,
  `tests/fixtures/java_pivot_output_snapshot_parity.json`, and
  `tests/integration/test_java_pivot_output_snapshot_parity.py`.
- Added Java two-level rowSubtotals + grandTotal output cases for flat rows and
  grid rows+columns over the same isolated neutral SQLite seed.
- Extended the neutral seed/replay contract with `subCategory`, matching Java's
  `product$subCategoryName` output.
- Fixed Python ordinary Pivot output post-processing to append additive
  row subtotal rows when `options.rowSubtotals=true`, while preserving the
  previous grandTotal-only path for requests without rowSubtotals.
- Focused Java exporter passed with SQLite-focused clean execution:
  `mvn clean test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`.
- Focused Python replay passed:
  `2 passed in 0.67s`.
- Remaining Pivot output gaps after P0-11: `parentShare` output snapshots,
  non-additive auxiliary requery snapshots, `baselineRatio` output snapshots,
  large-domain threshold/limit refusal snapshots, and pivot/domain governance
  propagation.

P0-12 follow-up:

- Extended the active P0-8/P0-10/P0-11 Pivot output snapshot producer/replay
  instead of creating a parallel fixture:
  `JavaPivotOutputSnapshotTest.java`,
  `tests/fixtures/java_pivot_output_snapshot_parity.json`, and
  `tests/integration/test_java_pivot_output_snapshot_parity.py`.
- Added Java flat/grid `parentShare` output cases over a neutral two-level row
  hierarchy with non-trivial shares: `0.75`, `0.25`, and `1`.
- Extended the neutral seed with a second electronics subcategory. Existing
  total expectations now use `400` instead of `350`.
- Updated Python replay canonicalization to include `share` in flat output when
  the request contains a mixed metric object named `share`.
- No Python production engine change was required; the first replay mismatch
  was in the replay canonicalizer, not the engine.
- Focused Java exporter passed with SQLite-focused execution:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`.
- Focused Python replay passed:
  `2 passed in 0.42s`.
- Remaining Pivot output gaps after P0-12: non-additive auxiliary requery
  snapshots, `baselineRatio` output snapshots, large-domain threshold/limit
  refusal snapshots, and pivot/domain governance propagation.

P0-13 follow-up:

- Extended the active Pivot output snapshot producer/replay with ordinary
  rows + columns `baselineRatio` cases:
  `JavaPivotOutputSnapshotTest.java`,
  `tests/fixtures/java_pivot_output_snapshot_parity.json`, and
  `tests/integration/test_java_pivot_output_snapshot_parity.py`.
- Added Python runtime support for Java-aligned `baselineRatio` on
  `axis=columns` with `baseline=first|last`.
- Updated Python DTO validation so `baselineRatio` requires columns axis and
  baseline, while `parentShare` remains rows-axis only.
- Focused Python replay passed:
  `17 passed in 0.53s`.
- Java exporter did not execute in this workspace because
  `foggy-dataset-model` testCompile fails on existing unrelated module
  classpath issues before `JavaPivotOutputSnapshotTest` runs.
- Remaining Pivot output gaps after P0-13: non-additive auxiliary requery
  snapshots, large-domain threshold/limit refusal snapshots, and pivot/domain
  governance propagation.

P0-14 follow-up:

- Extended the active Pivot output snapshot producer/replay with ordinary flat
  rowSubtotals + grandTotal non-additive output:
  `JavaPivotOutputSnapshotTest.java`,
  `tests/fixtures/java_pivot_output_snapshot_parity.json`, and
  `tests/integration/test_java_pivot_output_snapshot_parity.py`.
- Added Python runtime support for auxiliary total requery on generated ordinary
  Pivot subtotal and grand-total rows when a native metric aggregation is not
  `sum` or `count`.
- Focused Java exporter passed with SQLite-focused execution:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Focused Python replay passed:
  `2 passed in 0.43s`.
- Remaining Pivot output gaps after P0-14: grid/cascade/tree non-additive
  evidence, large-domain threshold/limit refusal snapshots, and pivot/domain
  governance propagation.

P0-15 follow-up:

- Extended the active P0-7 Pivot/domain transport snapshot producer/replay with
  large-domain threshold and renderer-limit cases:
  `JavaPivotDomainSnapshotTest.java`,
  `tests/fixtures/java_pivot_domain_snapshot_parity.json`, and
  `tests/integration/test_java_pivot_domain_snapshot_parity.py`.
- Added `domain-sqlite-large-501-transport` to prove the `>500` threshold path
  through a shared SQLite CTE renderer contract.
- Added `domain-sqlite-python-bind-limit-gap` to document that Java accepts
  1000 SQLite bind parameters under its larger guard while Python intentionally
  fails closed above 999 parameters.
- Focused Java exporter passed with SQLite-focused execution:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Focused Python replay passed:
  `2 passed in 0.39s`.
- Remaining Pivot/domain gaps after P0-15: grid/cascade/tree non-additive
  evidence, pivot/domain governance propagation, SQL Server cascade oracle, and
  MySQL 5.7 live support-scope evidence.

P0-16 follow-up:

- Extended the active governance snapshot producer/replay with Pivot and domain
  transport denied-column propagation:
  `JavaGovernanceSnapshotTest.java`,
  `tests/fixtures/java_governance_snapshot_parity.json`, and
  `tests/integration/test_java_governance_snapshot_parity.py`.
- Added neutral Java cases for Pivot row-axis relation field denial, Pivot
  `parentShare` native-metric dependency denial, and domain transport
  denied-column fail-closed behavior before transport SQL rendering.
- Governance manifest lane now advertises Pivot/domain transport governance
  propagation as active coverage.
- Focused Java exporter passed with SQLite-focused execution:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Focused Python replay passed:
  `2 passed in 0.64s`.
- Manifest replay passed:
  `6 passed in 0.66s`.
- Current full baseline after activating the P0-16 fixture first failed in two
  compose runtime pause/resume tests:
  `2 failed, 4039 passed, 232 skipped, 45 warnings in 17.58s`.
  A second full run failed in another compose runtime pause/resume test:
  `1 failed, 4040 passed, 232 skipped, 43 warnings in 17.82s`.
  All three observed failing tests passed when rerun directly, so the current
  full baseline is recorded as unstable rather than green.
- Remaining governance gaps after P0-16: authority-resolved visible model
  allow/deny, cross-model calculated-field refusals, sanitized error payloads,
  and aggregate-join governance propagation.
- Remaining Pivot/domain gaps after P0-16: grid/cascade/tree non-additive
  evidence, SQL Server cascade oracle, and MySQL 5.7 live support-scope
  evidence.

BUG-P0-17 follow-up:

- P0-16 full-baseline runs exposed intermittent compose runtime pause/resume
  failures where tests observed `run_ctx.state == SUSPENDED` before reading a
  non-null `run_ctx.suspension`.
- The fix keeps production runtime behavior unchanged and updates touched tests
  to wait through `SuspensionManager.get_active_suspension()` /
  `list_active_suspensions()`, which is the complete-publication boundary for
  state + `SuspensionResult` + wait slot.
- Focused pause/resume files passed:
  `24 passed in 0.29s`.
- Scoped ruff passed:
  `All checks passed!`.
- Compose runtime suite passed:
  `293 passed, 16 warnings in 1.01s`.
- Full Python pytest passed:
  `4041 passed, 232 skipped, 43 warnings in 18.02s`.

P0-18 follow-up:

- Extended the active governance snapshot producer/replay with
  authority-resolved visible-model allow/deny cases:
  `JavaGovernanceSnapshotTest.java`,
  `tests/fixtures/java_governance_snapshot_parity.json`, and
  `tests/integration/test_java_governance_snapshot_parity.py`.
- Added neutral Java cases proving the one-shot compile path uses
  `AuthorityResolutionPipeline.resolve` when explicit bindings are absent:
  - `authority-visible-model-allow-compiles`
  - `authority-visible-model-deny-missing-binding-fails-closed`
- The denied case fails closed with
  `compose-authority-resolve/model-binding-missing` at `authority-resolve`
  instead of falling through to plan-lower missing binding.
- Governance manifest lane now advertises authority-resolved visible-model
  allow/deny as active coverage.
- Focused Java exporter first hit a transient Maven incremental testCompile
  classpath failure on existing compose classes such as `CteUnit`,
  `JoinSpec`, and `CteComposer`; immediate rerun passed:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Scoped ruff passed:
  `All checks passed!`.
- Python replay plus manifest passed:
  `6 passed in 0.53s`.
- Full Python pytest passed:
  `4049 passed, 232 skipped, 43 warnings in 17.65s`.

P0-19 follow-up:

- Extended the active governance snapshot producer/replay with calculatedFields
  denied dependency refusal cases:
  `JavaGovernanceSnapshotTest.java`,
  `tests/fixtures/java_governance_snapshot_parity.json`, and
  `tests/integration/test_java_governance_snapshot_parity.py`.
- Added neutral Java cases for direct calculated dependency denial, transitive
  calculated dependency denial, and relation-field calculated dependency denial:
  - `query-denied-calculated-direct-dependency-refused`
  - `query-denied-calculated-transitive-dependency-refused`
  - `query-denied-calculated-relation-dependency-refused`
- Governance manifest lane now advertises calculatedFields denied dependency
  fail-closed behavior as active coverage.
- Focused Java exporter passed:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Scoped ruff passed:
  `All checks passed!`.
- Python replay plus manifest passed:
  `6 passed in 0.45s`.
- Full Python pytest passed:
  `4049 passed, 232 skipped, 43 warnings in 17.46s`.

P0-20 follow-up:

- Extended the active governance snapshot producer/replay with sanitized
  denied-column error payload checks:
  `JavaGovernanceSnapshotTest.java`,
  `tests/fixtures/java_governance_snapshot_parity.json`, and
  `tests/integration/test_java_governance_snapshot_parity.py`.
- Added neutral Java cases proving governance refusal errors expose the QM field
  marker but do not expose the denied physical table or column marker:
  - `query-denied-sanitized-measure-error-payload`
  - `query-denied-sanitized-relation-error-payload`
- Governance manifest lane now advertises sanitized governance error payloads
  as active coverage.
- Focused Java exporter first hit a transient Maven incremental
  testCompile/classpath failure on existing pivot/preagg classes; immediate
  rerun passed:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Scoped ruff passed:
  `All checks passed!`.
- Python replay plus manifest passed:
  `6 passed in 0.47s`.
- Full Python pytest passed:
  `4049 passed, 232 skipped, 43 warnings in 22.00s`.

P0-21 follow-up:

- Extended the active compose-script snapshot producer/replay with
  execute-mode rows envelope evidence:
  `JavaComposeScriptSnapshotTest.java`,
  `tests/fixtures/java_compose_script_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_snapshot_parity.py`.
- Added neutral Java case:
  - `execute-base-plan-rows-envelope`
- Compose script manifest lane now advertises execute rows replay as active
  coverage. Legacy `DataSetResult`/`ComposedDataSetResult` method-surface
  parity is no longer a default P0 target because current `dataset.compose_script`
  is QueryPlan-envelope based.
- Java exporter passed across default, MySQL, and Postgres surefire executions:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Python replay plus manifest passed:
  `8 passed in 0.45s`.
- Scoped ruff passed:
  `All checks passed!`.
- Full Python pytest passed:
  `4049 passed, 232 skipped, 43 warnings in 17.75s`.

P0-22 follow-up:

- Added a dedicated active MCP compose-script error payload snapshot lane:
  `JavaComposeScriptToolErrorSnapshotTest.java`,
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`.
- Added neutral Java/Python case:
  - `resolver-null-host-misconfig`
- The replay validates `status/error_code/phase`, absence of `model`, message
  markers, and forbidden stack/exception markers.
- Java `foggy-dataset-mcp` module-local focused Maven execution was later
  reclassified by P0-39 as a missing-`-am` reactor verification issue, not a
  current source/test drift.
- The new exporter compiles standalone with the module classpath and was
  executed through reflection to generate the Python fixture.
- Python focused replay plus manifest passed:
  `6 passed, 1 warning in 0.59s`.
- Scoped ruff passed:
  `All checks passed!`.
- Full Python pytest passed:
  `4051 passed, 232 skipped, 44 warnings in 17.70s`.

P0-23 follow-up:

- Extended the dedicated MCP compose-script error payload snapshot lane with
  remote authority-binding principal mismatch:
  `JavaComposeScriptToolErrorSnapshotTest.java`,
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`.
- Added neutral Java/Python case:
  - `remote-principal-mismatch`
- The replay validates `compose-authority-resolve/principal-mismatch`,
  `permission-resolve`, absence of `model`, message markers, and forbidden
  stack/exception markers.
- Java `foggy-dataset-mcp` module-local focused Maven execution was later
  reclassified by P0-39 as a missing-`-am` reactor verification issue, not a
  current source/test drift.
- The updated exporter compiles standalone with the module classpath and was
  executed through reflection to generate the two-case Python fixture.
- Python focused replay plus manifest passed:
  `6 passed, 2 warnings in 0.56s`.
- Scoped ruff passed:
  `All checks passed!`.
- Full Python pytest passed:
  `4051 passed, 232 skipped, 45 warnings in 18.01s`.

P0-24 follow-up:

- Aligned Python remote compose missing authority-binding behavior with Java:
  `compose-authority-resolve/invalid-response` in `permission-resolve`.
- Extended the dedicated MCP compose-script error payload snapshot lane:
  `JavaComposeScriptToolErrorSnapshotTest.java`,
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`.
- Added neutral Java/Python case:
  - `remote-missing-authority-binding`
- Updated Python binding unit coverage for the new error-code/phase contract.
- Java `foggy-dataset-mcp` module-local focused Maven execution was later
  reclassified by P0-39 as a missing-`-am` reactor verification issue, not a
  current source/test drift.
- The updated exporter compiles standalone with the module classpath and was
  executed through reflection to generate the three-case Python fixture.
- Python focused replay, binding test, and manifest passed:
  `7 passed, 4 warnings in 0.52s`.
- Scoped ruff is blocked by existing file-wide lint debt in touched files:
  `src/foggy/mcp/tools/compose_script_tool.py` typing-modernization findings
  and `tests/test_mcp/test_compose_script_tool_binding.py`
  import/whitespace findings.
- Full Python pytest passed:
  `4051 passed, 232 skipped, 46 warnings in 17.31s`.

P0-25 follow-up:

- Extended the dedicated MCP compose-script error payload snapshot lane with
  input/context validation cases:
  `JavaComposeScriptToolErrorSnapshotTest.java`,
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`.
- Added neutral Java/Python cases:
  - `missing-script`
  - `missing-context`
- Aligned Python missing script behavior to Java's `missing-script` error code.
- Aligned Python missing context behavior to Java's `internal-error` payload.
- Java exporter compiles standalone with the module classpath and was executed
  through reflection to generate the five-case Python fixture.
- Python focused replay, input/context unit checks, and manifest passed:
  `9 passed, 6 warnings in 0.54s`.
- Java `foggy-dataset-mcp` module-local focused Maven execution was later
  reclassified by P0-39 as a missing-`-am` reactor verification issue, not a
  current source/test drift.
- Scoped ruff is blocked by existing file-wide lint debt in touched files:
  `src/foggy/mcp/tools/compose_script_tool.py` typing-modernization findings
  and `tests/test_mcp/test_compose_script_tool.py` import/typing findings.
- Full Python pytest passed:
  `4051 passed, 232 skipped, 47 warnings in 19.98s`.
- Resolver factory exception behavior was later closed by P0-34.

P0-26 follow-up:

- Extended the dedicated MCP compose-script error payload snapshot lane with
  header bridge cases:
  `JavaComposeScriptToolErrorSnapshotTest.java`,
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`.
- Added neutral Java/Python cases:
  - `missing-user-id-header`
  - `missing-namespace-header`
- Aligned Python context bridge failures from missing header-mode principal or
  namespace to Java's `internal-error` payload.
- Added `X-NS` namespace header alias support after `X-Namespace`.

P0-27 follow-up:

- Extended the compose-script runtime snapshot lane with `pure_runtime`
  capability policy allow/deny cases:
  `JavaComposeScriptSnapshotTest.java`,
  `tests/fixtures/java_compose_script_snapshot_parity.json`, and
  `tests/integration/test_java_compose_script_snapshot_parity.py`.
- Added Python runtime preflight for registered-but-denied compose runtime
  capability calls so the denial remains fail-closed and names the capability
  instead of surfacing a generic fsscript null-call error.

P0-28 follow-up:

- Added a neutral domain/question runner adapter design that keeps P0 scope on
  Java-exported request/tool-argument fixtures and Python replay infrastructure.
- Explicitly deferred Odoo business model packs, registry pulls, and generated
  model refresh until neutral engine replay is active.

P0-29 follow-up:

- Python now has Java-aligned runtime `dictionaryDiscovery` metadata parsing,
  V3 JSON/markdown exposure, sensitive/hidden/error fail-closed handling, and
  context-scoped discovery cache isolation.
- Keep domain-specific aliases in model packs. The engine owns only the generic
  opt-in discovery contract and metadata behavior.

P0-30 follow-up:

- Python now has core Java-aligned `semanticScaleFactor` support for fact
  properties, dimension properties, measures, `formulaDef` /
  `dialectFormulaDef` results, query SQL, calculated-field references, and V3
  metadata.
- P0-32 closed the neutral snapshot catalog promotion with Java-exported helper,
  SQL, metadata, and fail-closed cases replayed by Python.
- P0-33 closed the stricter Java-style explicit HAVING aggregate alias
  validation gap while preserving Python aggregate-slice auto-lift
  compatibility.
- Remaining semantic scale gaps are namespace-level opt-out parity and live DB
  result parity.

P0-31 follow-up:

- Activated the neutral domain/question runner lane with Java-exported
  normalized `dataset.query_model` tool arguments and Python replay.
- First fixture covers grouped query, calculated/time-window query, and
  denied-field fail-closed behavior.
- Kept LLM transcript evaluation, Odoo packs, registry pull, and generated model
  refresh out of this P0 lane.

P0-32 follow-up:

- Promoted semantic scale into the active Java snapshot parity manifest as
  `semanticScaleFactor`.
- Added Java exporter and Python replay for helper literal formatting,
  dimension-property SQL, aggregate alias HAVING SQL, calculatedFields,
  formula-backed properties, V3 metadata, and invalid carrier-column
  validation.
- Recorded the Java/Python calculated-field parameterization difference through
  separate `javaParams` and `pythonParams` fixture expectations.

P0-34 follow-up:

- Extended the dedicated MCP compose-script error payload snapshot lane with
  `resolver-factory-exception`.
- Aligned Python generic resolver factory exceptions from
  `host-misconfig/internal` to Java's `internal-error/internal`.
- Kept resolver factory `None` as `host-misconfig/internal`.

P0-35 follow-up:

- Closed the selected aggregate alias shadowing gap left after P0-33.
- Python now rejects explicit HAVING references to aggregate aliases that
  collide with existing model fields, ignoring case, so
  `sum(salesAmount) as salesAmount` cannot make a base measure look like a
  selected aggregate alias in same-layer explicit HAVING.
- Distinct selected aggregate aliases remain valid in HAVING, including
  alias-to-alias comparisons.

P0-39 follow-up:

- Reclassified the recurring Java MCP `SemanticQueryRequest.OutputFormattingItem`
  testCompile failure as a module-local Maven classpath issue caused by running
  `-pl foggy-dataset-mcp` without `-am`.
- Established the focused Java MCP baseline:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=<TargetTest> -Dsurefire.failIfNoSpecifiedTests=false test`.
- Verified both `JavaComposeScriptToolErrorSnapshotTest` and
  `LocalDatasetAccessorGovernanceTest` with that reactor command.

P0-40 follow-up:

- Extended the dedicated MCP compose-script error payload snapshot lane with
  `resolver-resolve-exception`.
- Confirmed Java classifies generic resolver `resolve(...)` exceptions as
  `compose-authority-resolve/upstream-failure` with tool phase
  `permission-resolve`.
- Added Python replay coverage for the same upstream-failure payload; no Python
  tool implementation change was required.

P0-41 follow-up:

- Extended the neutral domain/question runner fixture envelope with
  `neutral-runner-case-summary` report metadata.
- Python replay now validates report tool/model/mode, status, warning count,
  error count, warning markers, and error code against deterministic semantic
  responses.
- Kept Java `ToolCallCollector`, live LLM, Odoo packs, registry pull, and
  generated model refresh outside this P0 lane.

P0-47 follow-up:

- Expanded the neutral domain/question runner fixture with unsupported
  construct cases for pivot+timeWindow, hidden axis functions, and cross-model
  join intent.
- Python replay now validates unsupported construct metadata in both error
  details and neutral case-summary reports, plus pivot and hints round-trip
  behavior.
- Java MCP reactor exporter was re-run successfully after unrelated Java
  compile drift was cleared.

P0-48 follow-up:

- Added `scripts/run-domain-question-neutral-runner.py` as the Python CLI
  wrapper for the neutral domain/question runner lane.
- The wrapper supports `--dry-run` summary output,
  `FOGGY_DOMAIN_QUESTION_NEUTRAL_FIXTURE` override, and default pytest replay
  plus manifest validation.
- The script keeps the lane LLM-free, Odoo-free, registry-free, and
  external-DB-free.

P0-49 follow-up:

- Closed the compose root-wrapper drift for
  `DerivedQueryPlan(source=JoinPlan|UnionPlan)`.
- Python now mirrors Java `compileDerived` by returning terminal
  `ComposedSql` when a derived source compiles to `ComposedSql`.
- Six formerly non-strict derived-over-composed compose snapshot cases now
  carry strict SQL-shape replay.

P0-50 follow-up:

- Promoted the final three successful compose snapshot cases to
  `strictSqlShape`.
- Current compose neutral fixture now has `16` successful cases and `16`
  strict SQL-shape contracts.
- Kept error cases on error-code/marker replay rather than root-wrapper shape
  assertions.

P0-42 follow-up:

- Extended the compose snapshot lane with projected source-alias shadowing
  refusal, union branch-alias refusal, union result-alias qualified refs, and
  MySQL8/SQL Server qualified source-alias slice/order markers.
- Java and Python now fail closed when a derived projection aliases a column to
  a visible source alias such as `sales`, preventing ambiguous follow-on refs.
- Python now matches Java's union-as-source alias boundary: branch aliases are
  hidden after `UNION`, while the union result alias can qualify output fields.
- Python SQL Server embedded composed-source compilation no longer emits
  `FROM (WITH` for the Java snapshot case.

P0-43 follow-up:

- Extended the compose snapshot fixture DSL with a test-only `reuseKey` so Java
  and Python replay can reconstruct the same base `QueryPlan` instance across
  branches.
- Added reused-base derived-join coverage for `left.*` / `right.*`
  projection, slice, and orderBy refs.
- Closed the P0-37 stable relation reuse qualified-ref residual without
  changing the user-facing compose API or the stable relation S7 snapshots.

P0-44 follow-up:

- Added SQL Server `derived(union(...))` fallback coverage using the union
  result alias in projection, slice, and orderBy.
- Java and Python now replay this shape while forbidding embedded
  `FROM (WITH`.
- Python also aligns root SQL Server derived-chain output to Java's subquery
  fallback contract instead of top-level CTE wrapping.
- Kept live SQL Server execution and broader cross-dialect golden SQL coverage
  outside this focused snapshot lane.

P0-45 follow-up:

- Aligned Python compose-level SQL Server CTE capability with Java
  `ComposePlanner`: `mssql` / `sqlserver` use subquery fallback in compose
  lowering.
- Kept lower-level `SqlServerDialect.supports_cte` unchanged so this remains a
  compose planner safety rule, not a global dialect capability rewrite.
- Added Java snapshot markers for MySQL 5.7, PostgreSQL, and SQL Server base
  CTE/subquery shape plus SQL Server join subquery fallback.
- Updated Python fallback tests and replayed Java compose snapshots.

P0-46 follow-up:

- Added Java-exported `expected.sqlShape` metadata to successful compose
  snapshot cases.
- Added `strictSqlShape` for frozen root-wrapper contracts, including base
  cross-dialect CTE/subquery cases and SQL Server fallback cases.
- Python replay now validates stable SQL structure keys for every successful
  compose snapshot and validates root CTE/subquery wrapping only for strict
  cases.
- P0-49 later promoted the remaining derived-over-composed root-wrapper cases
  to strict replay after Java/Python convergence.
- P0-50 later promoted the last three successful compose snapshot cases, so
  every current successful compose case now has strict SQL-shape replay.
- P0-52 later added an executable coverage inventory for the compose snapshot
  dialect/plan/status matrix, keeping the strict success guarantee visible
  while surfacing missing success cells for future targeted expansion.
- P0-53 later closed the first inventory gap with Java-exported MySQL8 join
  success evidence.
- P0-55 through P0-57 later added Java-exported PostgreSQL join, PostgreSQL
  top-level union, and SQL Server top-level union success evidence, moving the
  current successful compose strict SQL-shape replay count to `20/20`.
- P0-58 evaluated SQLite as a separate staged compose dialect lane; SQLite
  `base/derived/union/join` remains intentionally visible in the inventory
  until opened one cell at a time.
- P0-59 later added Java-exported MySQL 5.7 derived filter/order/limit
  fallback evidence, moving the current successful compose strict SQL-shape
  replay count to `21/21`.
- P0-60 later added Java-exported MySQL 5.7 top-level union evidence, moving
  the current successful compose strict SQL-shape replay count to `22/22`.
- P0-61 later opened the SQLite staged compose lane with Java-exported base CTE
  evidence, moving the current successful compose strict SQL-shape replay count
  to `23/23`.
- P0-62 later added Java-exported MySQL 5.7 join fallback evidence, moving the
  current successful compose strict SQL-shape replay count to `24/24` and
  completing the non-SQLite compose success matrix.
- P0-63 later added Java-exported SQLite derived filter/order/limit CTE
  evidence, moving the current successful compose strict SQL-shape replay count
  to `25/25`.
- P0-64 later added Java-exported SQLite top-level union evidence, moving the
  current successful compose strict SQL-shape replay count to `26/26`.
- P0-65 later added Java-exported SQLite join CTE evidence, moving the current
  successful compose strict SQL-shape replay count to `27/27` and closing the
  current target compose dialect/plan success inventory.
- P0-66 later refreshed the current Java timeWindow SQL snapshot. The snapshot
  now records 8 Java-success SQL cases plus one explicit `wow-week-happy`
  generation error for the current Java `salesDate$week` catalog/model drift,
  and Python replays every Java-success case through validate mode.
- P0-67 later closed that `wow-week-happy` drift by exposing logical
  `salesDate$week` in the Java ecommerce demo/query model, refreshing the Java
  snapshot to 9 SQL success cases with no generation errors, and making Python
  replay require the full 9-case success set.
- P0-68 later added Python SQLite live-result execution for the full
  Java-success timeWindow happy-case catalog, with deterministic execution
  ranges and result-level checks for comparative, cumulative, rolling, and
  post-calculated fields.
- P0-69 later hardened the Java-aligned `pivot + timeWindow` unsupported
  boundary across request parsing, validate/execute modes, governance query
  building, and Java neutral fixture real-service replay.
- P0-70 later hardened the domain transport boundary replay lane with explicit
  fixture-presence and parameterized replay for SQLite 501 transport, SQLite
  1000-bind fail-closed, empty-column refusal, and the MySQL 5.7 Java-only
  derived-table gap.
- P0-71 later added Java-fixture-driven SQLite live-result replay for the
  two-field NULL-safe and 501-member CTE transport domain plans.
- P0-72 later audited Java 9.2 QueryModel aggregate join against Python
  QueryModel, ordinary explicit join, governance, metadata, and compose
  landing points. The landing decision is to introduce a separate aggregate
  relation carrier after neutral snapshots exist, not to mutate ordinary
  explicit joins or start from Odoo business models.
- P0-73 later added the aggregate-join neutral snapshot contract fixture and
  planned manifest lane.
- P0-74 later added the Python contract replay skeleton and made
  `queryModelAggregateJoin` a required manifest feature.
- P0-75 later added the Java aggregate-join neutral snapshot exporter. P0-87
  later expanded that exporter to the 19-case `querymodel-aggregate-join-2`
  contract envelope at
  `target/parity/_querymodel_aggregate_join_snapshot.json` for Python replay
  promotion.
- P0-76 later promoted that Java snapshot into a committed Python fixture and
  activated offline replay for SQL/result/error/metadata/diagnostics markers.
- P1-2 later added the first parser/loader fail-closed guard for unsupported
  aggregate join declarations and Java-style `leftJoinAggregate(...)` DSL
  sentinels.
- P0-77 later added the minimal Python aggregate relation carrier so DSL calls
  preserve filters, group keys, measures, aliases, and join conditions while the
  runtime path remains fail-closed.
- P0-78 later added loader-side carrier extraction for explicit aggregate
  relation dicts and Java-style DSL objects. The loader now reports recognized
  carrier counts while still failing closed.
- P0-79 adds the runtime/compiler refusal boundary around models carrying
  `aggregate_relations`: synchronous validate, async validate,
  `build_query_with_governance`, and direct `_build_query` all fail closed
  with sanitized `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED` before SQL generation.
- P0-80 adds a guarded loader attachment path:
  `load_models_from_directory(..., attach_aggregate_relations=True)` can attach
  parsed aggregate relation carriers to a QM alias while default loading remains
  fail-closed and runtime validate still refuses before SQL generation.
- P0-81 defines the minimal SQLite SQL-shape for aggregate relation lowering:
  one root model, one RHS grouped subquery, fixed RHS filters, relation-owned
  aggregate outputs, and Java fixture marker checks before runtime exposure.
- P0-82 implements the narrow SQLite aggregate relation lowering skeleton:
  one root model, one LEFT aggregate relation, RHS grouped subquery, fixed RHS
  filters, aggregate output projections, fallback alias/count-star handling,
  and missing right-key groupBy fail-closed behavior.
- P0-83 adds focused SQLite live-result parity for that happy path, proving the
  root-side measure is not multiplied by RHS fact rows.
- P0-84 adds the aggregate governance/metadata boundary: RHS denied physical
  source columns fail closed with an aggregate-specific code, and aggregate
  output lineage is attached to build columns.
- P0-85 adds the first deterministic pushdown diagnostics boundary: simple AND
  filters can push to RHS `where`/`having`, OR filters remain outer-only with a
  retained reason code, and runtime extData RHS filters resolve or fail closed.
- P0-86 inventories Java 9.2 aggregate relation acceptance evidence that was
  not represented in the original 10-case Python fixture.
- P0-87 expands the Java/Python fixture to 19 cases for fieldAccess,
  system_slice, denied-source dependency, calculated-field dependency, and raw
  accessBuilder governance replay. The first Python runtime slice now covers
  aggregate output fieldAccess allow/deny and system_slice guard no-leak in the
  narrow SQLite aggregate relation path, plus an explicit unreferenced RHS
  denied-source pass-through assertion and dynamic calculated-field direct/chain
  denied-source refusal plus predefined calculated-field dependency refusal and
  positive predefined calculated execution plus raw accessBuilder outer-only
  behavior.
- P0-88 implements the public API metadata contract for aggregate relation
  lineage through V3 metadata while filtering public `aggregateRelation` to the
  exact Java seven-key DTO.
- P0-89 starts SQL behavior expansion beyond governance/API metadata. Its four
  slices prove group-key alias request slices, derived relation
  parameter/explain behavior, structured RHS projection pruning/default
  aggregation, and mixed predicate boundaries in Python: the outer predicate
  uses the left request alias while RHS pushdown uses the mapped aggregate group
  key; fixed RHS filters, pushed RHS WHERE, pushed aggregate HAVING, outer
  predicates, SQLite EXPLAIN, and live execution share deterministic
  placeholder params; structured RHS projections omit unreferenced aggregate
  measures while raw SQL accessBuilder keeps full projection; mixed OR
  join-key/measure predicates remain outer-only with retained diagnostics; and
  explicit AND wrapper `in`/range predicates keep RHS WHERE/HAVING pushdown.
- P0-90 hardens the broader request-stage boundary for aggregate relations:
  registered-RHS tests now prove `groupBy`, `having`, `orderBy`,
  `returnTotal`, post stages, `timeWindow`, and internal `pivot` combinations
  fail closed before SQL generation without leaking physical table names.
- P0-79+ now records the aggregate-join continuation sequence as completed
  through P0-110, with P0-87 v2 snapshot/replay active, the
  first P0-87 runtime fieldAccess, system_slice, denied-source, dynamic
  calculated-denial, and predefined calculated-denial/predefined-execution plus
  raw accessBuilder outer-only slices complete, P0-88 public V3 metadata
  exposure implemented, and P0-89 group-key alias pushdown, derived relation
  parameter/explain behavior, RHS projection pruning/default aggregation, and
  mixed predicate boundaries locked by Python regression evidence. P0-90
  records the broader request-stage refusal boundary, P0-91 plans the next
  Java fixture export, P0-92/P0-93 promote the v3 29-case Java fixture into
  Python replay, P0-94 implements unsafe runtime-filter refusal, null-check
  outer-only predicates, and public diagnostics, P0-95 opens bounded `orderBy`
  and `returnTotal` support, P0-96 opens structured accessBuilder join-key
  pushdown, and P0-97 proves composite-key pushdown for the narrow SQLite
  aggregate relation path. P0-98 opens RHS dimension fixed-filter lowering
  inside the RHS aggregate subquery, and P0-99 opens left dimension keys in
  aggregate relation ON conditions. P0-100 opens request slices on left
  dimension keys that are also aggregate relation join keys. P0-101 keeps
  nested dimension `joinTo` paths fail-closed across RHS filters, left ON keys,
  and left request slices until Java nested-path fixture evidence and a
  dedicated lowering design exist. P0-102 opens a bounded O615-shaped
  no-columns, aliased-key, and scalar tenant guard/no-leak slice while keeping
  the full O615 explicit join graph fixture-led. P0-103 proves non-join-key
  root dimension property and dimension `$id` request slices stay outer-only,
  emit reachable root dimension joins, and do not push unreachable RHS aliases.
  P0-104 proves RHS dimension `$id` fixed filters lower inside the RHS
  aggregate subquery. P0-105 extends the same RHS dimension `$id` path to
  context-backed runtime filters with missing/unsafe fail-closed coverage.
  P0-106 locks multi-relation carriers as fail-closed before SQL generation.
  P0-107 extends nested dimension fail-closed evidence to RHS nested dimension
  `$id` filters. P0-108 extends nested dimension `$id` fail-closed evidence to
  left/root ON keys and request slices. P0-109 extends nested dimension
  fail-closed evidence to RHS runtime `$id` filters. P0-110 extends left/root
  nested dimension `$id` fail-closed evidence to runtime request slices.

Odoo registry consumer baseline:

- Python has `scripts/pull-odoo-models.py` and `scripts/check-model-drift.py`.
- Current `src/foggy/demo/models/odoo/models.lock.json` points to
  `foggy.odoo.community@1.1.9`.
- Java/registry promotion docs show current Odoo bundles at `1.1.10`.
- `scripts/check-model-drift.py --model-dir src/foggy/demo/models/odoo` fails:
  lock expects content checksum
  `sha256:93a4a5bee662baf1892a68e6196fdca9057a0215c66b97ad92de6ff48888219b`,
  directory is
  `sha256:584aa35377f23690f77670a203bb01a1d405c44d835550d88c1ecd2e762c39e4`.
- P0-54 proves consumer compatibility without refreshing generated models:
  local temp pulls of `foggy.odoo.community@1.1.10` and
  `foggy.odoo.pro@1.1.10` pass checksum/drift checks and Python loader
  compatibility with namespace `odoo`.

## Gap Matrix

Risk levels:

- High: likely correctness/security/parity regression if implemented or exposed.
- Medium: implemented core exists but current Java snapshot parity is not proven.
- Low: mostly documentation/test harness/status drift.

Priorities:

- P0: phase-one validation and low-risk alignment foundation.
- P1: bounded engine parity fixes after P0 evidence is stable.
- P2: larger feature work or business/domain-heavy work.

| Capability | Java current status | Python current status | Parity gap | Risk | Priority | Recommended verification |
| --- | --- | --- | --- | --- | --- | --- |
| Compose Query / derived query / relation reuse | `compose-query.md` marks QueryPlan base/derived/union/join, CTE/subquery, script runtime, second-stage compute, and cross-DB `joinInMemory` complete. Java v3.0 adds qualified join field/source alias parity and fail-closed source-alias ambiguity handling. P0-37/P0-42 add source alias projection/slice/order, derived inheritance, projected source-alias shadowing, and union-as-source alias boundary snapshots. P0-46 adds SQL-shape metadata to the active compose snapshot fixture. P0-49 freezes derived-over-composed root-wrapper shape. P0-50 makes every current successful compose snapshot strict on SQL shape. P0-52 adds an executable dialect/plan/status coverage inventory. P0-53 adds MySQL8 join success evidence. P0-55 through P0-57 add PostgreSQL join/union and SQL Server top-level union success evidence. P0-59 adds MySQL 5.7 derived fallback evidence. P0-60 adds MySQL 5.7 top-level union evidence. P0-61 adds SQLite base CTE evidence. P0-62 adds MySQL 5.7 join fallback evidence. P0-63 adds SQLite derived CTE evidence. P0-64 adds SQLite union evidence. P0-65 adds SQLite join CTE evidence. | Python has `engine/compose` with plan, schema, relation, compilation, runtime, security, sandbox, authority, and MCP `ComposeScriptTool`. P0-37/P0-42/P0-44/P0-45/P0-46/P0-49/P0-50 replay Java compose snapshots and add focused join/union/dialect regressions for duplicate aliases, projected alias shadowing, union branch-alias refusal, union result-alias qualified refs, SQL Server union-as-derived fallback, compose-level SQL Server CTE capability, structural SQL shape replay, derived-over-composed terminal SQL parity, and full strict SQL-shape replay for successful cases. P0-52 keeps the matrix visible before adding new golden SQL cases; P0-53 closes the MySQL8 join cell; P0-55/P0-56/P0-57 close PostgreSQL join/union and SQL Server union cells; P0-59/P0-60/P0-62 close the MySQL 5.7 derived/union/join cells; P0-61/P0-63/P0-64/P0-65 close the SQLite base/derived/union/join cells. | Core alias/source-scope behavior and selected dialect fallback behavior are now covered by active Java/Python replay, including stable SQL-shape keys and strict root-wrapper checks for all successful compose cases. The current target compose dialect/plan success inventory has no missing success cells; unresolved lexical-scope contracts should stay fail-closed until Java freezes the contract. | Medium | P0/P1 | Keep Java compose snapshot replay active against plan schema, SQL shape, error code, script output, and the coverage inventory. Add targeted dialect-specific SQL shape cases only when the inventory shows a meaningful missing cell or Java drift is observed. |
| SQL compilation / CTE / union / join | Java supports Base/Derived/Union/Join QueryPlan, dialect CTE/subquery strategy, real SQL parity, and SQL Server subquery fallback. P0-42 explicitly forbids embedded `FROM (WITH` for SQL Server qualified source-alias slice/order. P0-44 adds SQL Server `derived(union(...))` fallback and root derived-chain subquery markers. P0-45 adds cross-dialect base/join CTE/subquery markers. P0-46 exports compact SQL shape manifests with strict root-wrapper flags for frozen fallback contracts. P0-49 freezes Java/Python derived-over-join and derived-over-union root wrapper parity. P0-50 closes remaining successful SQL-shape strictness. P0-52 exposes current missing success cells before expanding golden SQL. P0-53 adds MySQL8 join CTE shape evidence. P0-55/P0-56/P0-57 add PostgreSQL join CTE, PostgreSQL top-level union, and SQL Server top-level union shape evidence. P0-59 adds MySQL 5.7 derived subquery fallback shape evidence. P0-60 adds MySQL 5.7 top-level union evidence. P0-61 adds SQLite base CTE evidence. P0-62 adds MySQL 5.7 join subquery fallback evidence. P0-63 adds SQLite derived CTE evidence. P0-64 adds SQLite top-level union evidence. P0-65 adds SQLite join CTE evidence. Java 9.2 additionally accepted QueryModel aggregate join; P0-75 exports its neutral SQL/result/governance/diagnostics/metadata contract and P0-87 expands it to the 19-case v2 governance fixture. | Python M6/M7 implemented `compile_plan_to_sql`, CTE/subquery fallback, union/join tests, relation outer runtime, and stable relation snapshots. P0-42 adds SQL Server embedded composed-source fallback and union-as-source result alias qualified refs. P0-44 aligns root SQL Server derived chains to subquery fallback and replays SQL Server union-as-derived fallback. P0-45 treats `mssql` / `sqlserver` as compose-level subquery fallback dialects while preserving lower-level dialect metadata. P0-46 replays stable SQL-shape keys for every successful compose snapshot and full root wrapper shape for strict cases. P0-49 returns terminal `ComposedSql` for derived-over-composed sources. P0-50 confirmed `16/16` successful compose cases were strict; P0-53 moved the count to `17/17`; P0-55/P0-56/P0-57 moved it to `20/20`; P0-59 moved it to `21/21`; P0-60 moved it to `22/22`; P0-61 moved it to `23/23`; P0-62 moved it to `24/24`; P0-63 moved it to `25/25`; P0-64 moved it to `26/26`; P0-65 moves it to `27/27`. P0-52 makes the dialect/plan matrix executable. P0-82/P0-83 add the first QueryModel aggregate relation SQLite SQL and live-result boundary. P0-87 replays Java v2 governance SQL/error/result markers and implements the first runtime fieldAccess/system_slice/denied-source/calculated/predefined-denial/predefined-execution/raw-access slices before broadening further. P0-88 exposes the public V3 metadata DTO for aggregate relation outputs. P0-89 adds explicit group-key alias request-slice pushdown/live-result, derived relation parameter/explain, RHS projection pruning/default aggregation, and mixed OR / AND in-range predicate boundary coverage. | General compile path is close for current neutral snapshots. The narrow QueryModel aggregate relation SQLite happy path, V3 metadata DTO, v2 governance fixture, group-key alias request-slice behavior, derived relation parameter/explain behavior, RHS projection pruning/default aggregation, and mixed predicate boundary are now covered; remaining compile gaps are external aggregate relation dialects, broader QueryModel stages, richer optimizer diagnostics, and richer live DB proof. | High | P0/P1 for snapshot parity and narrow SQLite aggregate relation boundary; P2 for external aggregate relation dialects and broad runtime implementation | P0/P1: continue targeted cross-dialect golden SQL snapshots for base/derived/union/join only when the coverage inventory shows a meaningful missing cell or drift appears. Aggregate relation follow-up should request Java fixtures for the now-Python-covered mixed predicate contract plus broader request stages and external dialect SQL/result evidence before broad exposure. |
| Script/runtime tool | Java has `dataset.compose_script`, legacy `DataSetResult` / `ComposedDataSetResult` internals, `QueryPlan.execute/to_sql`, script parity tests, and tool-level MCP entry. P0-4 exports tool markers, runtime globals, basic result shape, preview SQL capture, security fail-closed cases, and forbidden markers that keep legacy result-object methods out of the AI-facing script tool. P0-21 adds execute-mode rows envelope replay for `return { plans: dsl(...) }`. P0-22 adds a dedicated MCP host-misconfig error payload snapshot for resolver-null. P0-23 adds remote authority-binding principal-mismatch error payload replay. P0-24 adds remote missing authority-binding invalid-response replay. P0-25 adds missing script and missing ToolExecutionContext payload replay. P0-26 adds missing `X-User-Id` and `X-Namespace` header bridge payload replay. P0-27 adds `pure_runtime` capability policy allow/deny replay. P0-34 adds generic resolver factory exception payload replay. P0-40 adds resolver `resolve(...)` upstream-failure payload replay. | Python has `ComposeScriptTool`, ContextVar runtime bundle, `execute_sql`, plan execution, capability registry/library loader, JS fixture parity tests, and MCP binding tests. P0-4 replay validates shared tool markers, forbidden legacy result markers, and runtime cases; P0-21 replay validates execute-mode `plans` row-list shape; P0-22/P0-23/P0-24/P0-25/P0-26/P0-34/P0-40 replay structured host/remote/input/context/header/resolver-factory/resolver-resolve error fields and forbidden leakage markers; P0-27 replay validates capability allow/deny and Python now preflights registered-but-denied capability calls with a named fail-closed error. README still says `dataset.compose_query` is pending. | Neutral snapshot lane is active through tool markers, runtime globals, preview SQL capture, fail-closed security parameters, execute rows envelope, resolver-null host-misconfig, resolver factory exception internal-error, resolver `resolve(...)` upstream-failure permission-resolve, remote principal mismatch, remote missing authority binding, missing script, missing context, missing user/namespace headers, capability allow/deny, and the current boundary that legacy result-object methods are not part of `dataset.compose_script`. Remaining gap is a decision on Python's extra fsscript globals. Legacy DataSetResult/ComposedDataSetResult parity should only reopen if product explicitly revives that API. | Medium | P0/P1 | Keep P0-4/P0-21/P0-22/P0-23/P0-24/P0-25/P0-26/P0-27/P0-34/P0-40 replay active; decide whether Python's extra fsscript globals remain accepted divergence before reopening script API expansion. |
| Permission / visible model / denied columns | Java 9.x preserves governance across queryModel, pivot, domain transport, and aggregate join; visible model and denied column behavior is fail-closed. P0-5/P0-6 now export neutral `ModelBinding`, compiler forwarding, missing-binding fail-closed, denied-column mapping, query validation, and metadata trimming snapshots. P0-16 adds Pivot and domain transport denied-column propagation snapshots. P0-18 adds authority-resolved visible-model allow/deny snapshots. P0-19 adds calculatedFields direct, transitive, and relation dependency denial snapshots. P0-20 adds sanitized governance error payload snapshots. P0-87 adds aggregate relation fieldAccess, system slice, unrelated denied-source, calculated dependency, predefined calculated, and raw accessBuilder governance evidence. | Python has authorization tests, compose authority/security tests, visible/denied logic in semantic service, and v1.15 acceptance for governance cross-path behavior. P0-5/P0-6 replay validates the corresponding Python boundary plus real Python `SemanticQueryService` mapping/query/metadata behavior. P0-16 replays Pivot and domain transport fail-closed validation with deniedColumns. P0-18 replays one-shot authority resolution through `compile_plan_to_sql(..., bindings=None)`. P0-19 replays calculatedFields denial through the real `SemanticQueryService` validation path. P0-20 replays sanitized error payload constraints by checking forbidden physical markers are absent. P0-84 adds aggregate relation RHS source physical-column denial for the narrow SQLite path. P0-87 replays the new aggregate governance fixture cases offline and adds runtime aggregate-output fieldAccess allow/deny, system_slice guard no-leak behavior, unreferenced RHS denied-source pass-through, dynamic calculated direct/chain denied-source refusal, predefined calculated dependency refusal, positive predefined calculated execution, and raw accessBuilder outer-only behavior for the narrow SQLite aggregate relation path. P0-88 adds public V3 metadata governance for aggregate output `visible_fields` and RHS denied-source hiding. | Neutral governance lane is active through authority-resolved visible-model allow/deny, queryModel denied-column validation including calculatedFields dependencies, sanitized error payload checks, metadata trimming, Pivot/domain transport propagation, aggregate relation RHS source-column denial, public aggregate output metadata trimming, Java-exported aggregate governance case evidence, and the first aggregate runtime fieldAccess/system_slice/unreferenced-denied-source/dynamic-calculated/predefined-denial/predefined-execution/raw-access slices. Remaining gaps are broader aggregate governance positives and external dialects. Current Odoo/domain fixture layer is stale and cannot prove latest business visible-model coverage. | High | P0/P1 for regression evidence and narrow aggregate source denial; P2 for broad aggregate join governance | Keep P0-5/P0-6/P0-16/P0-18/P0-19/P0-20/P0-84/P0-87/P0-88 replay active. Next governance work should add broader positive matrix evidence only after dialect contracts are explicit. |
| Inline formula / calculated fields / alias behavior | Java includes formula compiler parity, predefined formula fixes, inline formula/calculated fields, alias behavior, v3.0 semantic money scale, and 9.2 formula follow-ups. | Python has formula compiler/capability tests, formula field extraction, semantic service formula compiler, timeWindow/calculatedFields history, v1.16 same-stage alias fix, P0-33 explicit HAVING aggregate-alias strictness, P0-35 explicit HAVING aggregate alias field-collision refusal, and P0-36 refreshed formula parity/QM audit evidence. Formula focused pytest is green and the demo QM audit has zero compiler-incompatible non-window formulas. | Core aggregate alias boundaries and current formula audit evidence are tighter, but post-aggregate calculated-field staging and any newly exported Java formula follow-up cases remain open. | High | P0/P1 | Keep P0-36 formula audit active. P1: implement bounded formula gaps only when a new snapshot proves drift; include alias-in-slice/order/group tests, post-aggregate staging refusals, and semantic scale golden result cases. |
| Time window / relative date | Java supports timeWindow in query paths; pivot forbids direct timeWindow and routes time intelligence through calculated fields. P0-66 refreshed the current Java SQL snapshot for timeWindow happy cases and P0-67 closed the `wow-week-happy` `salesDate$week` catalog/model drift. | Python has `time_window.py`, Java parity catalog fixture, refreshed Java SQL snapshot replay, SQLite execution, real DB matrix tests, and v1.15 acceptance for timeWindow. P0-67 requires 9 Java-success SQL snapshots with no Java generation errors and replays every Java-success case through Python validate mode. P0-68 executes the full Java happy-case catalog against SQLite and checks result semantics for comparative, cumulative, rolling, and post-calculated fields. P0-69 hardens the `pivot + timeWindow` fail-closed boundary across runtime, governance, and Java neutral fixture replay. | Core timeWindow validate/SQLite coverage is active, the previous WoW week fixture drift is closed, Python now has live-result evidence for all current Java-success happy cases, and direct Pivot mutual-exclusion stability is covered. Remaining gaps are full normalized SQL diff for multi-CTE timeWindow SQL and Java-vs-Python live-result snapshots if Java exports stable embedded result evidence. | Medium | P1 | Keep P0-67 snapshot replay, Java catalog replay, P0-68 SQLite live-result execution, and P0-69 refusal tests active. Next timeWindow work should wait for a stable Java live-result snapshot or observed drift. |
| Pivot / subtotal / non-additive / baseline ratio | Java 9.0/9.1 has Pivot DSL, flat/grid/tree boundaries, subtotals/grand totals, non-additive aux requery, parentShare, baselineRatio, Stage5A domain transport, Stage5B rows two-level cascade, and explicit fail-closed cases. P0-7 exports neutral Pivot DTO and ordinary flat translation contracts; P0-8/P0-10/P0-11/P0-12/P0-13/P0-14 cover real SQLite flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio plus ordinary flat non-additive subtotal/grandTotal output snapshots; P0-15 covers the SQLite `>500` domain transport threshold and Python SQLite bind-limit refusal as a documented gap; P0-16 covers Pivot/domain denied-column governance propagation. Tree+cascade, outer pivot cache, SQL Server cascade, and conservative MySQL/MySQL5.7 cascade remain deferred/refused. | Python v1.8-v1.15 docs and tests show Pivot V9 flat/grid, contract shell, domain transport, cascade semantics/totals, MySQL57 and SQL Server refusal matrices, parentShare unit coverage, and v1.15 accepted parity baseline. P0-7 replay validates Pivot DTO parsing and ordinary flat translation through `validate_and_translate_pivot`; P0-8/P0-10/P0-11/P0-12/P0-13/P0-14 replay real flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio/non-additive-total SQLite output; P0-15 replays large-domain renderer behavior; P0-16 replays Pivot/domain governance propagation; P0-9 fixes Pivot output-shape cache-key isolation; P0-69 hardens the `pivot + timeWindow` unsupported boundary. | DTO/ordinary translation, real flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio/non-additive-total output evidence, output cache isolation, large-domain SQLite renderer evidence, Pivot/domain governance propagation evidence, and direct timeWindow mutual-exclusion evidence are now active. P0-13 closes the Python runtime gap for ordinary columns-axis `baselineRatio`; P0-14 closes the ordinary generated-total gap for non-additive native metrics by auxiliary requery; P0-15 documents Python's stricter SQLite bind limit. Still missing grid/cascade/tree non-additive evidence. Any tree/cascade extension should remain out of phase one. | High | P2 for deferred features | Keep P0-7/P0-8/P0-9/P0-10/P0-11/P0-12/P0-13/P0-14/P0-15/P0-16/P0-69 active. P2: tree+cascade, outer cache, SQL Server cascade, MySQL5.7 live evidence. |
| Domain transport / large domain fail-closed | Java 9.1 Stage5A uses internal `DomainTransportPlan`, request/context carriers, dialect renderers for SQLite/Postgres/MySQL8/MySQL5.7, OR-of-AND threshold, large-domain transport, and fail-closed limits. P0-7 exports SQLite/Postgres/MySQL8 renderer contracts plus Java MySQL5.7 derived-table support; P0-15 adds SQLite 501-tuple transport evidence and the Java-accepted/Python-refused 1000-bind documented gap. | Python has `semantic/pivot/domain_transport.py`, domain transport queryModel tests, real DB matrix tests, and v1.15 acceptance for SQLite/MySQL8/Postgres plus MySQL5.7 refusal. P0-7 replay validates SQLite/Postgres/MySQL8 fragments, params, NULL-safe predicates, and empty-column refusal. P0-15 validates Python SQLite CTE rendering for 501 params and fail-closed behavior for 1000 params. P0-70 makes the boundary cases an explicit named replay set. P0-71 executes Java-exported SQLite domain plans against SQLite and compares live results with oracle SQL. | Shared renderer evidence is active and now includes Java-fixture-driven SQLite live-result replay. Explicit gaps remain: Java MySQL8 uses `VALUES ROW(?)` while Python uses CTE `UNION ALL SELECT`, Java supports MySQL5.7 derived-table transport while Python intentionally fails closed for `mysql5.x`, and Java/Python SQLite parameter guards differ (`1000` accepted by Java but refused by Python). Direct axis-domain API and external dialect live-result replay still need snapshots where fixtures are available. | High | P0/P1 | Keep P0-7/P0-15/P0-70/P0-71 active. Next export direct axis-domain API behavior or external-dialect live-result parity for supported dialects; require an explicit product decision before implementing MySQL 5.7 derived-table transport in Python. |
| Model registry consumer | Java and registry have current Odoo package promotion at `foggy.odoo.community@1.1.10` and `foggy.odoo.pro@1.1.10`, pull scripts, addon sync, lock update, and drift checks. | Python has pull and drift scripts from earlier v1.0 work. P0-54 adds readonly local-registry temp-dir evidence for community/pro `1.1.10`: bundle checksum, temp lock drift check, and `load_models_from_directory(..., namespace="odoo")` compatibility for representative new TM/QM names. The committed demo lock remains `foggy.odoo.community@1.1.9` and the committed demo directory still fails drift check. | Consumer compatibility is no longer unproven, but the committed generated Odoo model directory is stale and drifted. Since phase one avoids Odoo business model expansion, generated-model refresh remains explicitly deferred. | High | P1/P2 | Keep P0-54 readonly integration test active. P2: update committed Odoo bundle only after engine snapshot gates pass and user approves touching generated Odoo files. |
| Domain fixtures and question runner | Java 9.1 has domain fixture packs, `scripts/run-ai-domain-direct.sh`, Odoo direct baseline suites, report/warning collection, tool argument rule warnings, and model registry promotion evidence. P0-31 adds a Java neutral exporter for normalized `dataset.query_model` tool arguments. P0-41 extends that neutral fixture with case-summary report metadata. P0-47 adds unsupported construct fail-closed cases. P0-51 adds deterministic `ToolCallCollector`-backed record envelopes. | Python has unit/integration tests, Odoo demo models, P0-31 replay for Java-exported neutral grouped, calculated/time-window, and denied-field fail-closed cases, P0-41 replay for optional report metadata, P0-47 replay for unsupported construct metadata, P0-48 `scripts/run-domain-question-neutral-runner.py` wrapper for dry-run summary plus default replay/manifest validation, and P0-51 replay for collector envelope fields. It still has no full AI domain direct runner. | Neutral replay is active, so Python can now prove normalized request/tool-argument compatibility, warning/report metadata, unsupported construct fail-closed metadata, local runner ergonomics, and deterministic collector envelope compatibility without LLM or Odoo. Remaining gaps are later Odoo packs and full direct runner coverage after registry/model drift is resolved. | High | P0/P1 | Keep P0-31/P0-41/P0-47/P0-48/P0-51 fixture replay and script wrapper active. P2: add Odoo packs only after registry/model drift is resolved. |
| Runtime dictionary discovery metadata | Java has `DbDictionaryDiscoveryDef`, runtime `DictionaryDiscoveryService`, metadata/markdown exposure, sensitive/hidden/error fail-closed handling, and model-level tests. | P0-29 adds the Python contract, loader parsing, V3 JSON/markdown exposure, context-scoped cache isolation, and focused regression tests. | Core metadata behavior is aligned. Remaining gap is whether to add this to the neutral Java/Python snapshot catalog. | Medium | P0/P1 | Keep P0-29 focused tests active; add neutral fixtures only if dictionary discovery becomes part of the shared snapshot catalog. |
| Semantic scale / money units | Java v3.0 introduces `semanticScaleFactor` for monetary/unit semantics and rejects arbitrary SQL fragment shortcuts. P0-32 adds Java snapshot evidence for helper literals, SQL rewriting, metadata, and carrier-column refusal. | P0-30 adds Python helper validation, field carriers, loader parsing, formulaDef/dialectFormulaDef value resolution, scaled query SQL, calculated-field reuse, and V3 metadata exposure. P0-32 replays Java semantic-scale snapshots, P0-33 aligns explicit HAVING to the selected aggregate-alias path, and P0-35 prevents explicit HAVING from using aggregate aliases that shadow existing fields. | Core engine behavior and neutral snapshot evidence are active. Remaining gaps are namespace-level opt-out config parity and live DB/result parity. | High | P1 | Keep P0-30/P0-32/P0-33/P0-35 focused tests active; add namespace opt-out or live DB evidence only when product/runtime needs it. |
| QueryModel aggregate join | Java 9.2 accepted Java-only aggregate join: RHS preaggregation before LEFT JOIN, same datasource, fixed/runtime RHS filters, permission/system slice preservation, source physical deniedColumns mapping, calculatedFields dependency propagation, metadata lineage, pushdown diagnostics, group-key alias request slices, derived relation parameter binding/explain behavior, RHS projection pruning/default aggregation with raw SQL accessBuilder fallback, mixed OR / AND in-range predicate boundaries, aggregate output `orderBy`, `returnTotal`, null-check outer-only predicates, composite keys, dimension-path keys/filters, O615 alias/no-column/tenant guard regressions, and real SQLite/MySQL 5.7 evidence. P0-75 adds a neutral exporter, `JavaQueryModelAggregateJoinSnapshotTest`, covering SQL/result, fail-closed, runtime filter, diagnostics, governance, and metadata cases. P0-87 expands the exporter to `querymodel-aggregate-join-2` with 19 cases, adding fieldAccess, system slice, unrelated denied-source, calculated dependency, predefined calculated execution, and raw accessBuilder evidence. P0-92 expands the exporter to `querymodel-aggregate-join-3` with 29 cases for `orderBy`, `returnTotal`, null-check diagnostics, public debug diagnostics, composite/dimension fixture evidence, structured accessBuilder pushdown evidence, and unsafe runtime-filter refusal. Java still carries PostgreSQL and production TMS DB evidence as follow-up risks. | P0-72 confirms Python has ordinary explicit QM joins, compose derived/join SQL, metadata v3, and governance lanes, but initially lacked RHS preaggregation lowering, aggregate output source lineage, pushdown diagnostics, aggregateRelation metadata runtime exposure, or runtime aggregate-join fixture replay. P0-73/P0-74 add the neutral snapshot contract and replay skeleton. P0-75 records the Java exporter/output path in the manifest. P0-76 commits the Java snapshot fixture and activates offline replay for SQL/result/error/metadata/diagnostics markers. P1-2 adds loader fail-closed handling for explicit aggregate join declarations and Java-style `leftJoinAggregate(...)` sentinels. P0-77 adds the minimal Python aggregate relation carrier and model landing point. P0-78 adds loader-side carrier extraction and refusal messages that report recognized carrier counts. P0-79 adds runtime/compiler refusal for unsupported models carrying `aggregate_relations`. P0-80 adds guarded loader attachment. P0-81 defines the SQLite SQL shape. P0-82/P0-83 implement and execute the narrow SQLite happy path. P0-84 adds RHS denied-source governance and internal lineage metadata. P0-85 adds deterministic pushdown diagnostics and runtime extData filter fail-closed behavior. P0-87 promotes the committed fixture/replay lane to the 19-case v2 governance contract and implements the first runtime fieldAccess/system_slice/unreferenced-denied-source/dynamic-calculated/predefined-denial/predefined-execution/raw-access slices. P0-88 exposes public V3 aggregate relation metadata with exactly the Java seven-key `aggregateRelation` DTO while keeping internal semantic-unit lineage private. P0-89 adds focused Python SQLite regressions and runtime lowering for group-key alias request-slice pushdown/live-result behavior, derived relation parameter/explain behavior, structured RHS projection pruning/default aggregation with raw SQL accessBuilder fallback, and mixed OR / AND in-range predicate boundaries. P0-90 records the registered-RHS fail-closed boundary for broader request stages. P0-93 promotes the Java v3 29-case fixture into Python replay. P0-94 implements unsafe runtime-filter refusal, null-check outer-only predicates, public diagnostics, and aggregate relation group-key schema validation. P0-95 implements bounded aggregate-output `orderBy` and `returnTotal`, P0-96 implements structured accessBuilder join-key equality pushdown, P0-97 proves composite-key pushdown, P0-98 implements RHS dimension fixed-filter lowering, P0-99 implements left dimension ON-key lowering, P0-100 implements left dimension request-slice pushdown, P0-101 proves nested `joinTo` paths fail closed for RHS filters, left ON keys, and left request slices, P0-102 proves the bounded no-columns/aliased-key/scalar-tenant-guard subset, P0-103 proves non-join-key dimension property/`$id` request slices stay outer-only without unreachable RHS alias pushdown, P0-104 proves RHS dimension `$id` fixed filters lower inside the RHS aggregate subquery, P0-105 proves RHS dimension `$id` runtime filters resolve from context with missing/unsafe fail-closed behavior, P0-106 proves multi-relation carriers fail closed before SQL generation, P0-107 extends nested dimension fail-closed coverage to RHS nested dimension `$id` filters, P0-108 extends nested dimension `$id` fail-closed coverage to left/root ON keys and request slices, P0-109 extends nested dimension fail-closed coverage to RHS runtime `$id` filters, and P0-110 extends left/root nested dimension `$id` fail-closed coverage to runtime request slices. | Python now has the first executable aggregate relation runtime boundary for SQLite: carrier, guarded attachment, SQL lowering, live result, source-column denial, metadata lineage, public V3 metadata exposure, pushdown diagnostics, runtime filter resolution, unsupported-shape fail-closed behavior, Java v3 snapshot replay, aggregate output fieldAccess allow/deny, system_slice guard no-leak behavior, unreferenced RHS denied-source pass-through, dynamic calculated direct/chain denied-source refusal, predefined calculated dependency refusal, positive predefined calculated execution through model predefined calculated fields, raw accessBuilder outer-only behavior, group-key alias request-slice pushdown, derived relation parameter/explain behavior, RHS projection pruning/default aggregation, mixed OR outer-only diagnostics, explicit AND wrapper `in`/range RHS pushdown, unsafe runtime value refusal, null-check outer-only behavior, public `debug.extra` diagnostics, bounded `orderBy`/`returnTotal` support, structured accessBuilder join-key pushdown, composite-key pushdown proof, RHS dimension fixed-filter lowering, RHS dimension `$id` fixed/runtime-filter lowering, left dimension ON-key lowering, left dimension request-slice pushdown, nested dimension fail-closed coverage including RHS and left/root nested dimension `$id` plus RHS nested runtime `$id` and left/root runtime `$id` request slices, no-columns default projection with an aliased join key, scalar tenant system-slice RHS pushdown/no-leak behavior, non-join-key dimension property/`$id` request-slice outer-only evidence, and multi-relation fail-closed evidence. Remaining gaps are external dialect parity, positive nested dimension-path lowering, positive multi-relation planning, unsupported broader stages (`groupBy`, `having`, post stages, `timeWindow`, pivot combinations), full O615 explicit join graph behavior including exported concrete RHS dimension `$id` request cases, richer optimizer diagnostics, and production TMS DB evidence. | High | P0/P1 for the narrow SQLite parity boundary and follow-up fixture evidence; P2 for broad SQL/runtime implementation | Keep Java v3 fixture replay plus P0-102 through P0-110 runtime tests active. Next bounded work should review positive nested dimension paths, full O615 explicit join graph boundaries, and external dialect evidence. Broader MySQL/PostgreSQL/TMS DB parity remains after SQLite closure. |

## Phase One Recommendation

Phase one should avoid large engine rewrites and avoid Odoo business model
expansion. The highest return is to make Python able to prove parity against the
current Java snapshots first.

Recommended first three work items:

1. **Java snapshot replay harness for engine-neutral cases**
   - Import or generate read-only Java snapshots for compose SQL/runtime,
     formula/catalog, timeWindow, pivot contract, and domain transport.
   - Keep fixtures engine-neutral: sales/orders/service-ticket style cases, not
     Odoo-specific business semantics.
   - Acceptance: Python pytest can run a focused `java_snapshot_parity` suite
     and either pass or produce explicit fail-closed mismatch records.

2. **Formula and calculated-field baseline repair**
   - P0-36 refreshed formula parity and QM audit evidence.
   - Current formula focused pytest is green; demo QM audit exits zero with
     window formulas classified separately from FormulaCompiler failures.
   - Acceptance: keep `tests/integration/test_formula_parity.py`, the formula
     focused suite, and `scripts/audit_qm_formulas.py --root src/foggy/demo`
     green as new Java catalog cases are added.

3. **Compose + Pivot smoke parity pack**
   - Compose: derived/union/join, source aliases, qualified join refs, SQL
     Server fallback, script tool schema, execute rows envelope, and
     structured MCP error payloads.
   - Pivot: flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio/non-additive
    contract, domain transport large-domain behavior, and fail-closed
    snapshots.
   - Acceptance: targeted tests pass locally without requiring external DBs;
     external DB lanes are marked/skipped consistently when fixtures are absent.

4. **Governance neutral snapshot pack**
   - Start with non-Odoo snapshots for `ModelBinding`, compile forwarding, and
     missing-binding fail-closed behavior.
   - P0-6 has extended the lane with denied physical-column mapping,
     queryModel column/orderBy refusal, and metadata trimming.
   - P0-16 has extended this lane with Pivot/domain transport denied-column
     propagation.
   - P0-18 has extended this lane with authority-resolved visible-model
     allow/deny.
   - P0-19 has extended this lane with calculatedFields direct, transitive,
     and relation dependency denial.
   - P0-20 has extended this lane with sanitized governance error payload
     checks.
   - Remaining governance extension is aggregate-join propagation, deferred to
     P2.
   - Acceptance: Java producer and Python replay agree on structured error codes
     and governance request/context payloads.

5. **Aggregate join snapshot contract, not implementation**
   - P0-72 freezes the gap audit and Python landing points.
   - P0-73 defines the required Java neutral aggregate-join fixture contract.
   - P0-74 adds Python manifest/replay scaffolding before production SQL
     generation.
   - P0-75 adds the Java neutral exporter and target snapshot output path.
   - P0-76 promotes the Java snapshot into a committed Python fixture and
     activates offline replay.
   - P1-2 adds the first fail-closed loader guard so recognized aggregate join
     declarations cannot load as ordinary joins.
   - P0-77 through P0-85 now carry this from missing parity lane to a narrow
     SQLite runtime boundary: carrier, guarded attachment, SQL lowering, live
     result, governance, metadata, diagnostics, and runtime filter evidence.
   - P0-87/P0-88/P0-89 extend that boundary with governance replay/runtime
     slices, public V3 metadata, group-key alias request-slice pushdown, derived
     relation parameter/explain behavior, and RHS projection pruning/default
     aggregation.
   - Acceptance: aggregate join remains engine-neutral and fixture-driven, with
     broad dialect/product exposure deferred until more Java/Python evidence is
     available.

## Executable Plan

### P0: Evidence and Low-Risk Harness

Expected modules/files:

- `tests/integration/` for Java snapshot parity tests.
- `tests/fixtures/` for normalized Java snapshot inputs/expected outputs.
- Possibly a small test utility under `tests/support/` if the repo already has a
  suitable convention; avoid production engine changes unless required.
- Docs under `docs/v3.8-python-alignment/` for evidence updates.

Tasks:

1. Freeze current baseline:
   - Record `.venv/bin/python -m pytest --tb=short -q` result.
   - Record formula snapshot failures and Postgres fixture absence.
   - Record Odoo model drift but do not resync generated Odoo files.
2. Define Java snapshot export list:
   - Compose query SQL/runtime: derived, union, join, source aliases, qualified
     refs, relation reuse, SQL Server fallback.
   - Formula/calculated fields: scalar/aggregate, alias in slice/order/group,
     predefined formulas, semantic scale if snapshot exists.
   - Time window: fixed date ranges, relative dates, rolling windows, pivot
     refusal.
   - Pivot/domain transport: flat/grid, parentShare, baselineRatio,
     non-additive totals, large-domain transport/refusal.
3. Add Python replay tests that do not require Odoo or live external DBs.
4. Normalize external DB tests:
   - Local SQLite is mandatory.
   - MySQL/Postgres/SQL Server lanes must skip or be separately profiled when
     endpoints are unavailable.

Exit criteria:

- Focused parity suite exists and can be run in local Python `.venv`.
- Full pytest no longer has evidence-only failures from broken formula snapshots.
- Remaining external DB failures are either fixed by local service availability
  or correctly skipped with explicit fixture prerequisites.

### P1: Bounded Engine Alignment

Expected modules/files:

- `src/foggy/dataset_model/semantic/`
- `src/foggy/dataset_model/engine/compose/`
- `src/foggy/dataset_model/semantic/pivot/`
- `scripts/pull-odoo-models.py` and `scripts/check-model-drift.py` only for
  dry-run/temp-dir validation, not committed generated Odoo updates.

Tasks:

1. Fix formula/calculated-field parity gaps proven by P0 snapshots.
2. Align compose dialect fallback and source alias behavior where Java snapshots
   show drift. P0-42 closes the projected source-alias shadowing and
   union-as-source alias boundary; P0-43 closes stable relation reuse
   qualified-ref replay; P0-44 adds SQL Server union-as-derived fallback.
   P0-45 aligns compose-level SQL Server CTE capability. P0-46 adds fixture
   SQL-shape manifests and strict root-wrapper checks for frozen fallback
   cases. P0-49 closes derived-over-composed root-wrapper parity for existing
   join/union snapshot cases. P0-50 makes every current successful compose
   snapshot strict for SQL-shape replay. P0-52 makes the coverage inventory
   executable. P0-53 and P0-55 through P0-57 close MySQL8 join, PostgreSQL
   join/union, and SQL Server union success cells. P0-58 keeps SQLite as a
   separate staged lane. P0-59 closes the MySQL 5.7 derived success cell.
   P0-60 closes the MySQL 5.7 union success cell. P0-61 opens the SQLite lane
   with base CTE evidence. P0-62 closes the MySQL 5.7 join success cell and
   completes the non-SQLite compose success matrix. P0-63 closes the SQLite
   derived success cell. P0-64 closes the SQLite union success cell. P0-65
   closes the SQLite join success cell and the current compose inventory.
3. Refresh timeWindow relative-date and pivot/domain-transport edge behavior.
   P0-66 closes the current timeWindow SQL snapshot refresh for the Java
   success set and records the then-current `wow-week-happy` Java drift.
   P0-67 closes that drift and makes the active snapshot lane 9 successful
   cases with no generation errors. P0-68 adds SQLite live-result execution
   for those 9 Java-success happy cases. P0-69 closes the direct
   `pivot + timeWindow` refusal-stability follow-up. P0-70 closes the current
   domain-transport refusal replay hardening for SQLite large/bind-limit,
   empty-column, and MySQL 5.7 Java-only gap cases. P0-71 adds SQLite
   live-result replay driven by Java-exported domain plans.
4. Add neutral domain fixture runner that can replay Java request/expected tool
   argument cases without Odoo models. P0-31/P0-41/P0-47/P0-48/P0-51 now
   cover neutral request replay, report metadata, unsupported construct
   metadata, the Python script wrapper, and deterministic `ToolCallCollector`
   record envelopes. Remaining work is later Odoo packs after drift is
   resolved.
5. Dry-run model registry consumer against `1.1.10` into temp output and verify
   loader compatibility. P0-54 closes this for local community/pro bundles
   without touching committed generated Odoo files.
6. Keep the QueryModel aggregate join P0 lane engine-neutral. P0-79 through
   P0-102 now close the first narrow SQLite boundary plus governance/API
   metadata/group-key alias, derived relation parameter/explain, RHS projection
   pruning, mixed predicate boundary, request-stage refusal slices, v3 fixture
   replay, unsafe runtime-filter refusal, null-check outer-only behavior,
   public diagnostics, bounded `orderBy` / `returnTotal`, structured
   accessBuilder join-key pushdown, composite-key pushdown proof, RHS
   dimension fixed-filter lowering, left dimension ON-key lowering, and left
   dimension request-slice pushdown, plus nested `joinTo` fail-closed
   coverage and a bounded O615-shaped no-columns/aliased-key/tenant guard
   slice; follow-up P0/P1 work should review the remaining replay-only v3
   cases before expanding behavior.

Exit criteria:

- Targeted Java snapshot parity tests pass for engine-neutral cases.
- Model registry consumer compatibility is proven without touching generated
  Odoo files.
- Any remaining differences have explicit Java/Python contract decisions.

### P2: Larger Feature Parity

Expected modules/files:

- Compose/query plan SQL compilation and runtime modules.
- Semantic query service and permission propagation.
- Pivot advanced semantics.
- Registry-generated Odoo models only after explicit approval.

Tasks:

1. Implement QueryModel aggregate join in Python if required:
   - Start from the P0-72 landing-point decision: use a separate aggregate
     relation carrier rather than ordinary explicit join mutation.
   - RHS preaggregation, fixed slice, group-key validation, permission/system
     slice preservation, runtime pushdown/refusal matrix.
   - P0-82 through P0-85 cover the first SQLite boundary, and P0-87 through
     P0-102 add the first runtime
     fieldAccess/system_slice/unreferenced-denied-source/dynamic
     calculated-denial/predefined-denial/predefined-execution/raw-access
     slices, public V3 metadata, group-key alias request-slice pushdown,
     derived relation parameter/explain behavior, RHS projection pruning, mixed
     predicate boundaries, unsafe runtime-filter refusal, null-check outer-only
     behavior, public diagnostics, bounded `orderBy` / `returnTotal`,
     structured accessBuilder join-key pushdown, composite-key pushdown, RHS
     dimension fixed-filter lowering, left dimension ON-key lowering, left
     dimension request-slice pushdown, and nested `joinTo` fail-closed
     coverage, plus the bounded O615 no-columns/aliased-key/tenant guard
     slice.
     Remaining P2 scope is external dialects, broader metadata shape evidence,
     multi-relation support, positive nested dimension path lowering, richer
     request-stage contracts, full O615 explicit join graph behavior, and
     production TMS DB evidence.
2. Add semantic scale namespace opt-out parity or live DB result evidence only
   if product/runtime needs it.
3. Add Odoo domain fixture packs and direct runner only after neutral fixture
   runner is stable.
4. Consider deferred pivot features:
   - tree+cascade,
   - outer pivot cache,
   - SQL Server cascade,
   - MySQL5.7 live large-domain evidence.

Exit criteria:

- Feature-specific design docs, tests, and acceptance evidence exist before
  production behavior is exposed.
- Odoo business model updates are isolated from engine parity work and gated by
  registry drift checks.

## Snapshot / Fixture Needs From Java

Required for P0:

- Compose query snapshots:
  - base/derived/union/join SQL and params,
  - source alias inheritance,
  - qualified `left.` / `right.` refs,
  - ambiguous alias refusals,
  - projected source-alias shadowing refusal,
  - union branch-alias refusal and union result-alias qualified refs,
  - SQL Server fallback expected SQL shape.
- Formula/calculated field snapshots:
  - catalog cases with stable ids,
  - generated SQL and params by dialect,
  - expected refusal/error codes,
  - predefined formula and alias placement cases.
- Time window snapshots:
  - fixed-date and relative-date requests,
  - generated SQL/params,
  - pivot refusal cases.
- Pivot/domain transport snapshots:
  - flat/grid output,
  - row subtotal/grandTotal output,
  - parentShare output,
  - baselineRatio cases,
  - ordinary non-additive aux requery output,
  - additional large-domain dialect/version gates beyond the P0-15 SQLite
    501/1000 snapshot cases.

Optional for P1/P2:

- Registry readonly temp-dir fixture for `foggy.odoo.community@1.1.10` and
  `foggy.odoo.pro@1.1.10` is active in P0-54.
- Domain question packs only after neutral runner support exists and
  registry/model drift is resolved.

## Current Largest Gaps

1. **Committed Odoo demo models are stale and drifted.**
   P0-54 proves the Python registry consumer can pull and load current
   community/pro `1.1.10` bundles from temp directories, but the committed demo
   lock is still `1.1.9` and local Odoo model files do not match that lock.
2. **Domain direct runner and Odoo packs remain deferred.**
   P0-51 closes deterministic collector-envelope replay for neutral cases, but
   Python still does not have full AI domain direct runner or Odoo pack replay
   evidence. Those should wait until registry/model drift is resolved.
3. **Aggregate join is partially proven for the narrow Python SQLite path; broad parity remains open.**
   P0-79 through P0-102 now provide carrier, guarded attachment, SQLite SQL/live
   result, governance, V3 metadata, diagnostics, Java v3 replay, null-check
   outer-only predicates, unsafe runtime-filter refusal, bounded `orderBy` /
   `returnTotal`, structured accessBuilder join-key pushdown, and composite-key
   pushdown proof, RHS dimension fixed-filter lowering, left dimension ON-key
   lowering, left dimension request-slice pushdown, and nested `joinTo`
   fail-closed coverage, plus bounded no-columns/aliased-key/tenant guard
   coverage. Remaining aggregate gaps are external dialects,
   positive nested dimension path lowering, non-join-key dimension-path request slices,
   multi-relation support, full O615 explicit join graph behavior, post stages, `groupBy`/`having`,
   `timeWindow`/pivot combinations, and production TMS DB evidence. Semantic
   scale core behavior is implemented in P0-30, neutral snapshots are active in
   P0-32, explicit HAVING alias strictness is aligned in P0-33, explicit HAVING
   aggregate alias field-collision refusal is active in P0-35, and P1-1 records
   the remaining semantic-scale choice between namespace opt-out and live
   DB/result evidence.
4. **External resource coverage remains environment-dependent.**
   P0-1 fixed one missing profile gate, but many Java-resource and external DB
   lanes still skip locally. Java snapshot replay should make the always-on
   engine-neutral subset stronger before product-facing claims.

## Non-Goals For This Round

- Commit/push only user-approved, current-iteration files; do not stage or
  clean unrelated Java/Python/registry dirty work.
- No rollback/cleanup of existing Java, Python, or registry dirty work.
- No generated Odoo model resync.
- No large production engine rewrite before Java snapshot parity gates exist.
- No Odoo business-model-first implementation.
