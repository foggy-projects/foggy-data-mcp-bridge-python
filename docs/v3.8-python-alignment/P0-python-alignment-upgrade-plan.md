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
| Compose Query / derived query / relation reuse | `compose-query.md` marks QueryPlan base/derived/union/join, CTE/subquery, script runtime, second-stage compute, and cross-DB `joinInMemory` complete. Java v3.0 adds qualified join field/source alias parity and fail-closed source-alias ambiguity handling. P0-37/P0-42 add source alias projection/slice/order, derived inheritance, projected source-alias shadowing, and union-as-source alias boundary snapshots. P0-46 adds SQL-shape metadata to the active compose snapshot fixture. P0-49 freezes derived-over-composed root-wrapper shape. P0-50 makes every current successful compose snapshot strict on SQL shape. | Python has `engine/compose` with plan, schema, relation, compilation, runtime, security, sandbox, authority, and MCP `ComposeScriptTool`. P0-37/P0-42/P0-44/P0-45/P0-46/P0-49/P0-50 replay Java compose snapshots and add focused join/union/dialect regressions for duplicate aliases, projected alias shadowing, union branch-alias refusal, union result-alias qualified refs, SQL Server union-as-derived fallback, compose-level SQL Server CTE capability, structural SQL shape replay, derived-over-composed terminal SQL parity, and full strict SQL-shape replay for successful cases. | Core alias/source-scope behavior and selected dialect fallback behavior are now covered by active Java/Python replay, including stable SQL-shape keys and strict root-wrapper checks for all successful compose cases. Remaining compose gaps are broader dialect matrix and unresolved lexical-scope contracts that should stay fail-closed until Java freezes the contract. | Medium | P0/P1 | Keep Java compose snapshot replay active against plan schema, SQL shape, error code, and script output. Add only targeted dialect-specific SQL shape cases when Java drift is observed. |
| SQL compilation / CTE / union / join | Java supports Base/Derived/Union/Join QueryPlan, dialect CTE/subquery strategy, real SQL parity, and SQL Server subquery fallback. P0-42 explicitly forbids embedded `FROM (WITH` for SQL Server qualified source-alias slice/order. P0-44 adds SQL Server `derived(union(...))` fallback and root derived-chain subquery markers. P0-45 adds cross-dialect base/join CTE/subquery markers. P0-46 exports compact SQL shape manifests with strict root-wrapper flags for frozen fallback contracts. P0-49 freezes Java/Python derived-over-join and derived-over-union root wrapper parity. P0-50 closes remaining successful SQL-shape strictness. Java 9.2 additionally accepted QueryModel aggregate join on Java only. | Python M6/M7 implemented `compile_plan_to_sql`, CTE/subquery fallback, union/join tests, relation outer runtime, and stable relation snapshots. P0-42 adds SQL Server embedded composed-source fallback and union-as-source result alias qualified refs. P0-44 aligns root SQL Server derived chains to subquery fallback and replays SQL Server union-as-derived fallback. P0-45 treats `mssql` / `sqlserver` as compose-level subquery fallback dialects while preserving lower-level dialect metadata. P0-46 replays stable SQL-shape keys for every successful compose snapshot and full root wrapper shape for strict cases. P0-49 returns terminal `ComposedSql` for derived-over-composed sources. P0-50 confirms `16/16` successful compose cases are strict. | General compile path is close for current neutral snapshots. Remaining gaps are broader cross-dialect golden SQL coverage and Java-only aggregate join. | High | P0/P1 for snapshot parity, P2 for aggregate join | P0/P1: continue targeted cross-dialect golden SQL snapshots for base/derived/union/join only when drift appears. P2: separate aggregate-join Python design with RHS preaggregation, permission propagation, and real DB parity. |
| Script/runtime tool | Java has `dataset.compose_script`, legacy `DataSetResult` / `ComposedDataSetResult` internals, `QueryPlan.execute/to_sql`, script parity tests, and tool-level MCP entry. P0-4 exports tool markers, runtime globals, basic result shape, preview SQL capture, security fail-closed cases, and forbidden markers that keep legacy result-object methods out of the AI-facing script tool. P0-21 adds execute-mode rows envelope replay for `return { plans: dsl(...) }`. P0-22 adds a dedicated MCP host-misconfig error payload snapshot for resolver-null. P0-23 adds remote authority-binding principal-mismatch error payload replay. P0-24 adds remote missing authority-binding invalid-response replay. P0-25 adds missing script and missing ToolExecutionContext payload replay. P0-26 adds missing `X-User-Id` and `X-Namespace` header bridge payload replay. P0-27 adds `pure_runtime` capability policy allow/deny replay. P0-34 adds generic resolver factory exception payload replay. P0-40 adds resolver `resolve(...)` upstream-failure payload replay. | Python has `ComposeScriptTool`, ContextVar runtime bundle, `execute_sql`, plan execution, capability registry/library loader, JS fixture parity tests, and MCP binding tests. P0-4 replay validates shared tool markers, forbidden legacy result markers, and runtime cases; P0-21 replay validates execute-mode `plans` row-list shape; P0-22/P0-23/P0-24/P0-25/P0-26/P0-34/P0-40 replay structured host/remote/input/context/header/resolver-factory/resolver-resolve error fields and forbidden leakage markers; P0-27 replay validates capability allow/deny and Python now preflights registered-but-denied capability calls with a named fail-closed error. README still says `dataset.compose_query` is pending. | Neutral snapshot lane is active through tool markers, runtime globals, preview SQL capture, fail-closed security parameters, execute rows envelope, resolver-null host-misconfig, resolver factory exception internal-error, resolver `resolve(...)` upstream-failure permission-resolve, remote principal mismatch, remote missing authority binding, missing script, missing context, missing user/namespace headers, capability allow/deny, and the current boundary that legacy result-object methods are not part of `dataset.compose_script`. Remaining gap is a decision on Python's extra fsscript globals. Legacy DataSetResult/ComposedDataSetResult parity should only reopen if product explicitly revives that API. | Medium | P0/P1 | Keep P0-4/P0-21/P0-22/P0-23/P0-24/P0-25/P0-26/P0-27/P0-34/P0-40 replay active; decide whether Python's extra fsscript globals remain accepted divergence before reopening script API expansion. |
| Permission / visible model / denied columns | Java 9.x preserves governance across queryModel, pivot, domain transport, and aggregate join; visible model and denied column behavior is fail-closed. P0-5/P0-6 now export neutral `ModelBinding`, compiler forwarding, missing-binding fail-closed, denied-column mapping, query validation, and metadata trimming snapshots. P0-16 adds Pivot and domain transport denied-column propagation snapshots. P0-18 adds authority-resolved visible-model allow/deny snapshots. P0-19 adds calculatedFields direct, transitive, and relation dependency denial snapshots. P0-20 adds sanitized governance error payload snapshots. | Python has authorization tests, compose authority/security tests, visible/denied logic in semantic service, and v1.15 acceptance for governance cross-path behavior. P0-5/P0-6 replay validates the corresponding Python boundary plus real Python `SemanticQueryService` mapping/query/metadata behavior. P0-16 replays Pivot and domain transport fail-closed validation with deniedColumns. P0-18 replays one-shot authority resolution through `compile_plan_to_sql(..., bindings=None)`. P0-19 replays calculatedFields denial through the real `SemanticQueryService` validation path. P0-20 replays sanitized error payload constraints by checking forbidden physical markers are absent. | Neutral governance lane is active through authority-resolved visible-model allow/deny, queryModel denied-column validation including calculatedFields dependencies, sanitized error payload checks, metadata trimming, and Pivot/domain transport propagation. Remaining gap is aggregate join governance, which stays P2 with the aggregate-join design line. Current Odoo/domain fixture layer is stale and cannot prove latest business visible-model coverage. | High | P0/P1 for regression evidence, P2 for aggregate join governance | Keep P0-5/P0-6/P0-16/P0-18/P0-19/P0-20 replay active. Next governance work should wait for aggregate-join design readiness or move to a different P0 lane. |
| Inline formula / calculated fields / alias behavior | Java includes formula compiler parity, predefined formula fixes, inline formula/calculated fields, alias behavior, v3.0 semantic money scale, and 9.2 formula follow-ups. | Python has formula compiler/capability tests, formula field extraction, semantic service formula compiler, timeWindow/calculatedFields history, v1.16 same-stage alias fix, P0-33 explicit HAVING aggregate-alias strictness, P0-35 explicit HAVING aggregate alias field-collision refusal, and P0-36 refreshed formula parity/QM audit evidence. Formula focused pytest is green and the demo QM audit has zero compiler-incompatible non-window formulas. | Core aggregate alias boundaries and current formula audit evidence are tighter, but post-aggregate calculated-field staging and any newly exported Java formula follow-up cases remain open. | High | P0/P1 | Keep P0-36 formula audit active. P1: implement bounded formula gaps only when a new snapshot proves drift; include alias-in-slice/order/group tests, post-aggregate staging refusals, and semantic scale golden result cases. |
| Time window / relative date | Java supports timeWindow in query paths; pivot forbids direct timeWindow and routes time intelligence through calculated fields. Compose docs mention rolling windows and pending MySQL8 lane evidence. | Python has `time_window.py`, Java parity catalog fixture, SQLite execution, real DB matrix tests, and v1.15 acceptance for timeWindow. | Mostly aligned. Need current Java snapshot refresh for relative dates and dialect behavior, plus confirm pivot rejection remains stable. | Medium | P1 | Replay Java time window catalog and real DB matrix where DB fixtures are available. Keep pivot+timeWindow refusal tests in P0 smoke set. |
| Pivot / subtotal / non-additive / baseline ratio | Java 9.0/9.1 has Pivot DSL, flat/grid/tree boundaries, subtotals/grand totals, non-additive aux requery, parentShare, baselineRatio, Stage5A domain transport, Stage5B rows two-level cascade, and explicit fail-closed cases. P0-7 exports neutral Pivot DTO and ordinary flat translation contracts; P0-8/P0-10/P0-11/P0-12/P0-13/P0-14 cover real SQLite flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio plus ordinary flat non-additive subtotal/grandTotal output snapshots; P0-15 covers the SQLite `>500` domain transport threshold and Python SQLite bind-limit refusal as a documented gap; P0-16 covers Pivot/domain denied-column governance propagation. Tree+cascade, outer pivot cache, SQL Server cascade, and conservative MySQL/MySQL5.7 cascade remain deferred/refused. | Python v1.8-v1.15 docs and tests show Pivot V9 flat/grid, contract shell, domain transport, cascade semantics/totals, MySQL57 and SQL Server refusal matrices, parentShare unit coverage, and v1.15 accepted parity baseline. P0-7 replay validates Pivot DTO parsing and ordinary flat translation through `validate_and_translate_pivot`; P0-8/P0-10/P0-11/P0-12/P0-13/P0-14 replay real flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio/non-additive-total SQLite output; P0-15 replays large-domain renderer behavior; P0-16 replays Pivot/domain governance propagation; P0-9 fixes Pivot output-shape cache-key isolation. | DTO/ordinary translation, real flat/grid/grandTotal/rowSubtotals/parentShare/baselineRatio/non-additive-total output evidence, output cache isolation, large-domain SQLite renderer evidence, and Pivot/domain governance propagation evidence are now active. P0-13 closes the Python runtime gap for ordinary columns-axis `baselineRatio`; P0-14 closes the ordinary generated-total gap for non-additive native metrics by auxiliary requery; P0-15 documents Python's stricter SQLite bind limit. Still missing grid/cascade/tree non-additive evidence. Any tree/cascade extension should remain out of phase one. | High | P2 for deferred features | Keep P0-7/P0-8/P0-9/P0-10/P0-11/P0-12/P0-13/P0-14/P0-15/P0-16 active. P2: tree+cascade, outer cache, SQL Server cascade, MySQL5.7 live evidence. |
| Domain transport / large domain fail-closed | Java 9.1 Stage5A uses internal `DomainTransportPlan`, request/context carriers, dialect renderers for SQLite/Postgres/MySQL8/MySQL5.7, OR-of-AND threshold, large-domain transport, and fail-closed limits. P0-7 exports SQLite/Postgres/MySQL8 renderer contracts plus Java MySQL5.7 derived-table support; P0-15 adds SQLite 501-tuple transport evidence and the Java-accepted/Python-refused 1000-bind documented gap. | Python has `semantic/pivot/domain_transport.py`, domain transport queryModel tests, real DB matrix tests, and v1.15 acceptance for SQLite/MySQL8/Postgres plus MySQL5.7 refusal. P0-7 replay validates SQLite/Postgres/MySQL8 fragments, params, NULL-safe predicates, and empty-column refusal. P0-15 validates Python SQLite CTE rendering for 501 params and fail-closed behavior for 1000 params. | Shared renderer evidence is active. Explicit gaps remain: Java MySQL8 uses `VALUES ROW(?)` while Python uses CTE `UNION ALL SELECT`, Java supports MySQL5.7 derived-table transport while Python intentionally fails closed for `mysql5.x`, and Java/Python SQLite parameter guards differ (`1000` accepted by Java but refused by Python). Direct axis-domain API and live DB result parity still need snapshots where fixtures are available. | High | P0/P1 | Keep P0-7/P0-15 active. Next export unsupported dialect refusal, MySQL version gates, max tuple/sql-size limits, direct axis-domain API behavior, and live DB result parity where fixtures are available. |
| Model registry consumer | Java and registry have current Odoo package promotion at `foggy.odoo.community@1.1.10` and `foggy.odoo.pro@1.1.10`, pull scripts, addon sync, lock update, and drift checks. | Python has pull and drift scripts from earlier v1.0 work, but current lock is `foggy.odoo.community@1.1.9`; local directory fails drift check; no evidence in this round that Python has consumed `1.1.10`. | Not absent, but stale and currently drifted. Since first phase avoids Odoo business model expansion, this should be treated as validation infrastructure debt, not first engine code work. | High | P1/P2 | P1: dry-run pull from local registry into a temp directory and verify checksum/loader compatibility. P2: update committed Odoo bundle only after engine snapshot gates pass and user approves touching generated Odoo files. |
| Domain fixtures and question runner | Java 9.1 has domain fixture packs, `scripts/run-ai-domain-direct.sh`, Odoo direct baseline suites, report/warning collection, tool argument rule warnings, and model registry promotion evidence. P0-31 adds a Java neutral exporter for normalized `dataset.query_model` tool arguments. P0-41 extends that neutral fixture with case-summary report metadata. P0-47 adds unsupported construct fail-closed cases. | Python has unit/integration tests, Odoo demo models, P0-31 replay for Java-exported neutral grouped, calculated/time-window, and denied-field fail-closed cases, P0-41 replay for optional report metadata, P0-47 replay for unsupported construct metadata, and P0-48 `scripts/run-domain-question-neutral-runner.py` wrapper for dry-run summary plus default replay/manifest validation. It still has no full AI domain direct runner. | Neutral replay is active, so Python can now prove normalized request/tool-argument compatibility, warning/report metadata, unsupported construct fail-closed metadata, and local runner ergonomics without LLM or Odoo. Remaining gaps are real Java `ToolCallCollector` export and later Odoo packs after registry/model drift is resolved. | High | P0/P1 | Keep P0-31/P0-41/P0-47/P0-48 fixture replay and script wrapper active. Next add deterministic `ToolCallCollector` export only when a non-LLM planner path is available. P2: add Odoo packs only after registry/model drift is resolved. |
| Runtime dictionary discovery metadata | Java has `DbDictionaryDiscoveryDef`, runtime `DictionaryDiscoveryService`, metadata/markdown exposure, sensitive/hidden/error fail-closed handling, and model-level tests. | P0-29 adds the Python contract, loader parsing, V3 JSON/markdown exposure, context-scoped cache isolation, and focused regression tests. | Core metadata behavior is aligned. Remaining gap is whether to add this to the neutral Java/Python snapshot catalog. | Medium | P0/P1 | Keep P0-29 focused tests active; add neutral fixtures only if dictionary discovery becomes part of the shared snapshot catalog. |
| Semantic scale / money units | Java v3.0 introduces `semanticScaleFactor` for monetary/unit semantics and rejects arbitrary SQL fragment shortcuts. P0-32 adds Java snapshot evidence for helper literals, SQL rewriting, metadata, and carrier-column refusal. | P0-30 adds Python helper validation, field carriers, loader parsing, formulaDef/dialectFormulaDef value resolution, scaled query SQL, calculated-field reuse, and V3 metadata exposure. P0-32 replays Java semantic-scale snapshots, P0-33 aligns explicit HAVING to the selected aggregate-alias path, and P0-35 prevents explicit HAVING from using aggregate aliases that shadow existing fields. | Core engine behavior and neutral snapshot evidence are active. Remaining gaps are namespace-level opt-out config parity and live DB/result parity. | High | P1 | Keep P0-30/P0-32/P0-33/P0-35 focused tests active; add namespace opt-out or live DB evidence only when product/runtime needs it. |
| QueryModel aggregate join | Java 9.2 accepted Java-only aggregate join: RHS preaggregation before LEFT JOIN, same datasource, fixed slice, permissions/system slice preserved, AND-only runtime pushdown, real SQLite/MySQL evidence. | No Python implementation evidence found in this audit. | Full feature gap. It is engine-level but not low risk, so it should not be phase-one implementation work. | High | P2 | New Python design doc and tests: AST/API contract, RHS aggregate plan, SQL generation, permission propagation, pushdown/refusal matrix, SQLite/MySQL/Postgres parity. |

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
   snapshot strict for SQL-shape replay. Broader dialect SQL-shape coverage
   remains open.
3. Refresh timeWindow relative-date and pivot/domain-transport edge behavior.
4. Add neutral domain fixture runner that can replay Java request/expected tool
   argument cases without Odoo models. P0-31/P0-41/P0-47/P0-48 now cover
   neutral request replay, report metadata, unsupported construct metadata, and
   the Python script wrapper. Remaining work is deterministic
   `ToolCallCollector` export and later Odoo packs after drift is resolved.
5. Dry-run model registry consumer against `1.1.10` into temp output and verify
   loader compatibility.

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
   - RHS preaggregation, fixed slice, group-key validation, permission/system
     slice preservation, runtime pushdown/refusal matrix.
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

- Registry dry-run fixture for `foggy.odoo.community@1.1.10` and
  `foggy.odoo.pro@1.1.10`.
- Domain question packs only after neutral runner support exists and
  registry/model drift is resolved.

## Current Largest Gaps

1. **Domain runner validation still lacks ToolCallCollector-backed export.**
   Python now has the neutral cross-language fixture runner and script wrapper,
   but the lane still uses deterministic neutral fixtures rather than a real
   Java `ToolCallCollector` export path.
2. **Registry/Odoo consumer is stale and drifted.**
   Python has consumer scripts, but the committed lock is `1.1.9`, Java/registry
   current is `1.1.10`, and local Odoo model files do not match the lock.
3. **Aggregate join is not proven in Python; semantic scale live evidence remains optional.**
   Aggregate join is Java-only in 9.2. Semantic scale core behavior is
   implemented in P0-30, neutral snapshots are active in P0-32, explicit HAVING
   alias strictness is aligned in P0-33, explicit HAVING aggregate alias
   field-collision refusal is active in P0-35, P1-1 records the remaining
   semantic-scale choice between namespace opt-out and live DB/result evidence,
   and P2-1 records the aggregate-join Python design boundary.
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
