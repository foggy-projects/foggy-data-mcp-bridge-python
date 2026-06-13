---
doc_purpose: Define the next Java snapshot expansion for aggregate relation governance parity.
version: v3.8-python-alignment
priority: P0-87
status: java-exported-python-replay-active-runtime-governance-slice-closed
owner: java-python-parity
---

# P0-87 QueryModel Aggregate Governance Snapshot Expansion

Date: 2026-06-12

## Scope

P0-87 defines and activates the next aggregate relation snapshot increment for
governance behavior that Java 9.2 acceptance covers and the previous Python
10-case fixture did not.

This is an exporter/snapshot and replay item first. Python runtime behavior for
the newly exported cases should expand only after the fixture contract is
reviewed. After fixture review, the first Python runtime slices cover aggregate
output `fieldAccess` allow/deny, `system_slice` guard no-leak behavior, an
explicit unreferenced denied-source pass-through assertion, dynamic
calculated-field direct/chain denied-source fail-closed behavior, and
predefined calculated-field denied-source fail-closed plus positive predefined
calculated-field execution behavior in the narrow SQLite aggregate relation
path. Raw SQL accessBuilder predicates are now retained on the root/outer
WHERE path and are not pushed into the RHS aggregate subquery. Odoo and
production business models remain out of scope.

## Current Baseline

The v1 Python fixture already covered:

- RHS preaggregation SQL shape for SQLite.
- Root-side measure non-multiplication live-result semantics.
- Missing RHS join-key groupBy refusal.
- Fixed RHS filters and runtime extData RHS filters.
- Simple AND pushdown diagnostics and OR outer-only diagnostics.
- Referenced denied RHS source physical-column refusal.
- Internal aggregate output lineage metadata.

The v2 Python fixture now also covers fieldAccess, system slice, unrelated
denied-source columns, raw accessBuilder boundaries, and calculated-field
dependency governance for aggregate relations. These are pinned as Java
snapshot replay evidence before broader Python runtime expansion.

## Required Java Exporter Cases

The exported stable case ids are:

| Proposed Case ID | Type | Required Contract |
| --- | --- | --- |
| `aggregate-join-field-access-allow-output` | sql or result | A request selecting an aggregate relation output passes when fieldAccess allows that output. |
| `aggregate-join-field-access-deny-output-refusal` | error | Denying the aggregate output alias fails closed with sanitized markers and without leaking physical RHS fields. |
| `aggregate-join-system-slice-guard-bypass-no-leak` | sql | A system slice required for governance is applied without requiring the guard field to be user-visible and without projecting it. |
| `aggregate-join-denied-source-column-unreferenced-pass` | sql or result | A denied RHS source physical column that is unrelated to selected aggregate outputs does not block the query. |
| `aggregate-join-calculated-field-denied-source-refusal` | error | A dynamic calculated field depending on a denied aggregate source fails closed. |
| `aggregate-join-calculated-field-chain-denied-source-refusal` | error | A transitive calculated dependency on a denied aggregate source fails closed. |
| `aggregate-join-predefined-calculated-field-denied-source-refusal` | error | A predefined calculated field depending on a denied aggregate source fails closed. |
| `aggregate-join-predefined-calculated-field-allowed-exec` | sql | A predefined calculated field over allowed aggregate relation data renders with stable SQL/result evidence. |
| `aggregate-join-raw-sql-access-builder-outer-only` | sql | Raw SQL accessBuilder predicates stay outside the RHS aggregate subquery. |

The Java exporter produced all planned P0-87 cases in
`querymodel-aggregate-join-2`. Follow-up optimizer/SQL details that were not
needed for this governance increment should move to P0-89.

## Python Replay Expectations

The Java exporter produced stable cases and Python replay now:

- Extends `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`
  from the Java output rather than hand-authoring expected behavior.
- Extends `tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py`
  to require the new case ids.
- Extends `tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py`
  to replay each new case by type and to pin row-level field leakage rules.
- Keep current runtime unsupported boundaries fail-closed where Python does not
  yet implement a positive Java behavior.

Expected Python behavior by group:

| Group | Initial Python Target |
| --- | --- |
| FieldAccess allow/deny | Implemented for aggregate output aliases in the narrow SQLite runtime path: non-empty `fieldAccess.visible` allows listed outputs and denies user-requested aggregate outputs with an aggregate-specific sanitized code. |
| System slice | Implemented for aggregate output guard predicates in the narrow SQLite runtime path: `system_slice` can reference an aggregate output without requiring it to be user-visible or projected; aggregate comparison filter ops are supported for this guard shape. |
| Unreferenced denied source | Runtime assertion now proves a known but unrelated RHS physical denied column does not block selected aggregate outputs and does not appear in generated SQL. |
| Calculated field denial | Dynamic calculated direct/chain dependency denial and predefined calculated dependency denial are implemented for aggregate outputs in the narrow SQLite runtime path. |
| Positive predefined calculated execution | Implemented for scalar model predefined calculated fields over aggregate relation outputs in the narrow SQLite runtime path; request-level custom calculatedFields still fail closed. |
| Raw accessBuilder | Implemented for model access SQL row filters in the narrow SQLite runtime path: raw predicates and bind params are appended to the root/outer WHERE and never pushed into the RHS aggregate subquery. |

## Exported Evidence

The Java exporter now writes
`foggy-dataset-model/target/parity/_querymodel_aggregate_join_snapshot.json`
with:

- `contractVersion = querymodel-aggregate-join-2`
- `dialect = sqlite`
- `19` cases, including all P0-87 governance additions.

The committed Python fixture copy is
`tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`.

## Non-Goals

- No external dialect aggregate relation support in this item.
- No Odoo, TMS, or registry-generated model refresh.
- No QueryFacade `returnTotal`, broad `orderBy`, or multi-relation runtime
  expansion.
- No public API DTO metadata changes in this item; P0-88 owns and implements
  that contract.

## Acceptance Criteria

- Java exporter has stable neutral cases for the required governance matrix or
  explicitly documents which proposed cases move to P0-89.
- Python committed fixture is regenerated from the Java output.
- Python replay tests pin new case ids, forbidden markers, error payload shape,
  diagnostics, and positive result semantics where applicable.
- Existing P0-82 through P0-85 fixture cases remain green.
- Any Python behavior that remains unsupported is represented by an explicit
  fail-closed or documented pending case, not by silent best-effort execution.

## Execution Check-In

- Status: Java exporter produced v2 governance cases; Python contract/manifest/
  replay is updated, and the focused Python SQLite runtime governance slice is
  active, including dynamic calculated direct/chain denial, predefined
  calculated dependency denial, positive predefined calculated execution, and
  raw accessBuilder outer-only behavior.
- Current Java impact: `JavaQueryModelAggregateJoinSnapshotTest` adds the v2
  aggregate governance cases and generated a 19-case SQLite snapshot.
- Current Python code impact: aggregate-aware `fieldAccess` validation now
  checks user-requested aggregate outputs before generic visible-field pruning,
  while intentionally excluding `system_slice` from user-field checks. Aggregate
  relation filter rendering now supports comparison operators needed by the
  Java v2 guard case. Aggregate denied-source validation now recursively expands
  user-selected dynamic calculated aliases and returns sanitized
  `error_detail.calculatedFields` alias chains for direct and transitive
  dependencies. It also expands model-defined predefined calculated aliases and
  fails closed with `error_detail.predefinedCalculatedFields` plus the aggregate
  source field when the predefined expression depends on a denied aggregate
  output. The aggregate relation SQLite builder now compiles scalar model
  predefined calculated fields over aggregate outputs through the existing
  FormulaCompiler, preserves SELECT bind-parameter ordering, and keeps custom
  request-level calculatedFields fail-closed. The aggregate relation SQLite
  builder also consumes model access row filters in the outer/root WHERE
  phase; SQL accessBuilder predicates retain their declared bind params and are
  intentionally not pushed into the RHS aggregate subquery.
- Current Python test impact: the SQLite aggregate relation test model declares
  an unrelated RHS `profitAmount` physical column so the v2 unreferenced
  denied-source case proves a known source column pass-through, not an unknown
  column no-op. The same focused suite now replays Java v2 direct and chained
  dynamic calculated-field denied-source refusal cases and the predefined
  calculated-field denied-source refusal case against the Python runtime. It
  also executes the Java predefined calculated-field allowed case against
  SQLite and asserts that custom request-level calculatedFields remain
  unsupported. It now executes the Java raw accessBuilder outer-only case,
  asserting Java fixture params, required outer SQL markers, forbidden RHS
  pushdown markers, and live SQLite row semantics.
- Current fixture impact:
  `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json` is
  regenerated from the Java v2 snapshot.
- Verification on 2026-06-12:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest=JavaQueryModelAggregateJoinSnapshotTest -Dfoggy.parity.snapshot=true -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  passed and produced `querymodel-aggregate-join-2`.
- Verification on 2026-06-12:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `10 passed in 0.08s`.
- Verification on 2026-06-12:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `20 passed in 0.54s`.
- Verification on 2026-06-12:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `35 passed in 0.63s`.
- Focused lint/checks on 2026-06-12:
  `.venv/bin/ruff check --select F src/foggy/dataset_model/aggregate_join.py src/foggy/dataset_model/semantic/service.py tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
  and `git diff --check` passed.
- Neighboring semantic regression on 2026-06-12:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_semantic_query.py tests/test_dataset_model/test_strict_column_resolution.py tests/test_dataset_model/test_window_functions.py -q`
  passed with `131 passed in 7.62s`.
- Full Python baseline on 2026-06-12:
  `.venv/bin/python -m pytest -q` passed with
  `4147 passed, 232 skipped, 53 warnings in 18.88s`.
- Remaining runtime gaps: external dialects and broader QueryModel stages
  remain follow-up.
