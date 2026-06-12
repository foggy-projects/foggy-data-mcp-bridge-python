---
doc_purpose: Define the next Java snapshot expansion for aggregate relation governance parity.
version: v3.8-python-alignment
priority: P0-87
status: ready-for-java-export
owner: java-python-parity
---

# P0-87 QueryModel Aggregate Governance Snapshot Expansion

Date: 2026-06-12

## Scope

P0-87 defines the next aggregate relation snapshot increment for governance
behavior that Java 9.2 acceptance covers but the current Python 10-case fixture
does not.

This is an exporter/snapshot planning item first. Python runtime changes should
wait until the Java fixture output is available and the replay contract is
reviewed. Odoo and production business models remain out of scope.

## Current Baseline

The active Python fixture already covers:

- RHS preaggregation SQL shape for SQLite.
- Root-side measure non-multiplication live-result semantics.
- Missing RHS join-key groupBy refusal.
- Fixed RHS filters and runtime extData RHS filters.
- Simple AND pushdown diagnostics and OR outer-only diagnostics.
- Referenced denied RHS source physical-column refusal.
- Internal aggregate output lineage metadata.

It does not cover fieldAccess, system slice, unrelated denied-source columns,
raw accessBuilder boundaries, or calculated-field dependency governance for
aggregate relations.

## Required Java Exporter Cases

The proposed stable case ids are:

| Proposed Case ID | Type | Required Contract |
| --- | --- | --- |
| `aggregate-join-field-access-allow-output` | sql or result | A request selecting an aggregate relation output passes when fieldAccess allows that output. |
| `aggregate-join-field-access-deny-output-refusal` | error | Denying the aggregate output alias fails closed with sanitized markers and without leaking physical RHS fields. |
| `aggregate-join-system-slice-guard-bypass-no-leak` | sql | A system slice required for governance is applied without requiring the guard field to be user-visible and without projecting it. |
| `aggregate-join-denied-source-column-unreferenced-pass` | sql or result | A denied RHS source physical column that is unrelated to selected aggregate outputs does not block the query. |
| `aggregate-join-calculated-field-denied-source-refusal` | error | A dynamic calculated field depending on a denied aggregate source fails closed. |
| `aggregate-join-calculated-field-chain-denied-source-refusal` | error | A transitive calculated dependency on a denied aggregate source fails closed. |
| `aggregate-join-predefined-calculated-field-denied-source-refusal` | error | A predefined calculated field depending on a denied aggregate source fails closed. |
| `aggregate-join-predefined-calculated-field-allowed-exec` | result | A predefined calculated field over allowed aggregate relation data executes with stable output. |
| `aggregate-join-raw-sql-access-builder-outer-only` | diagnostics | Raw SQL accessBuilder predicates stay outside the RHS aggregate subquery and report a stable outer-only reason. |

The last case is included because Java acceptance covers raw accessBuilder
outer-only behavior. If the Java exporter cannot produce it without introducing
unstable SQL text, it can move to the P0-89 SQL/diagnostics expansion.

## Python Replay Expectations

Once the Java exporter produces stable cases:

- Extend `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`
  from the Java output rather than hand-authoring expected behavior.
- Extend `tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py`
  to require the new case ids and forbidden leakage markers.
- Extend `tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py`
  to replay each new case by type.
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

- Status: ready for Java exporter work.
- Current Python code impact: none.
- Current fixture impact: none.
- Required next evidence: Java snapshot output containing the P0-87 case ids.
- Verification on 2026-06-12: existing aggregate relation manifest/contract/
  parity replay stayed green with `10 passed in 0.05s`.
- `git diff --check` passed.
