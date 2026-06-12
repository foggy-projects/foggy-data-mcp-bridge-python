---
doc_purpose: Define the next Java snapshot expansion for aggregate relation governance parity.
version: v3.8-python-alignment
priority: P0-87
status: java-exported-python-replay-active
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
reviewed. Odoo and production business models remain out of scope.

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
| FieldAccess allow/deny | Implement or validate governance resolution around aggregate outputs only after the fixture proves Java markers. |
| System slice | Merge governance predicates before aggregate lowering and verify the guard field is not projected or exposed as a user field. |
| Unreferenced denied source | Preserve P0-84 referenced-source refusal while allowing unrelated denied physical columns. |
| Calculated field denial | Ensure dynamic/predefined calculated dependency checks inherit aggregate source boundaries and fail closed with sanitized errors. |
| Positive predefined calculated execution | Treat as later implementation if it requires formula execution over aggregate outputs; do not fake parity in replay. |
| Raw accessBuilder | Keep raw predicates outer-only with a deterministic diagnostic reason before adding any pushdown behavior. |

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
- No public API DTO metadata changes; P0-88 owns that contract.

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
  replay is updated locally.
- Current Java impact: `JavaQueryModelAggregateJoinSnapshotTest` adds the v2
  aggregate governance cases and generated a 19-case SQLite snapshot.
- Current Python code impact: focused replay tests only; no broad runtime
  implementation for the newly exported governance behaviors yet.
- Current fixture impact:
  `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json` is
  regenerated from the Java v2 snapshot.
- Verification on 2026-06-12:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest=JavaQueryModelAggregateJoinSnapshotTest -Dfoggy.parity.snapshot=true -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  passed and produced `querymodel-aggregate-join-2`.
- Verification on 2026-06-12:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `10 passed in 0.08s`.
