---
doc_purpose: Plan the P0-79+ sequence for Python-Java QueryModel aggregate join alignment.
version: v3.8-python-alignment
priority: P0-79+
status: completed-through-P0-88-with-P0-87-runtime-fieldaccess-systemslice
owner: python-engine
---

# P0-79+ QueryModel Aggregate Join Roadmap

Date: 2026-06-12

## Scope Statement

The P0 line in `v3.8-python-alignment` is a Python engine to Java engine
alignment line. Work items should be engine-neutral and evidence-driven:
snapshot replay, fail-closed boundaries, compiler/runtime contracts, SQL shape,
metadata, governance, and live-result parity. Productization, Odoo business
model expansion, generated registry refreshes, UI behavior, and AI orchestration
are outside this line unless a separate approved work item says otherwise.

## Current State

- P0-72 froze the Python landing-point audit for Java 9.2 QueryModel aggregate
  join.
- P0-73 through P0-76 created and activated the Java neutral snapshot replay
  lane.
- P1-2 added the first parser/loader fail-closed guard.
- P0-77 added the aggregate relation carrier and model landing point.
- P0-78 added loader-side carrier extraction while still rejecting aggregate
  joins before runtime loading.
- P0-79 through P0-85 now complete the first narrow Python runtime boundary:
  guarded loader attachment, SQLite SQL lowering, SQLite live-result parity,
  RHS denied-source governance, aggregate output metadata lineage, pushdown
  diagnostics, and runtime extData filter fail-closed behavior.
- P0-86 inventories Java 9.2 aggregate relation acceptance evidence that was
  not represented in the earlier 10-case Java snapshot fixture.
- P0-87 expands the Java snapshot to the 19-case
  `querymodel-aggregate-join-2` governance fixture and activates Python replay
  for the new case ids. The first Python runtime slice now aligns aggregate
  output `fieldAccess` allow/deny and `system_slice` guard no-leak behavior in
  the narrow SQLite aggregate relation path.
- P0-88 freezes the public API metadata contract for aggregate relation lineage
  before Python exposes DTO behavior.

## Planned Sequence

| Item | Status | Purpose | Acceptance Gate |
| --- | --- | --- | --- |
| P0-79 runtime/compiler refusal boundary | Completed | Refuse any model carrying `aggregate_relations` before SQL generation until lowering exists. | Focused runtime/compiler refusal test plus existing loader and Java snapshot replay green. |
| P0-80 loader attachment behind refusal | Completed | Allow parsed aggregate carriers to attach to a QueryModel only in a controlled path that still refuses before SQL/runtime. | Loader can produce an alias model with `aggregate_relations` in a clearly guarded path; runtime still fails closed. |
| P0-81 minimal SQL-shape design for SQLite happy path | Completed | Define Python lowering shape for RHS grouped subquery and LEFT JOIN based on the committed Java fixture. | Design doc plus expected SQL markers; no broad runtime exposure. |
| P0-82 SQLite SQL lowering skeleton | Completed | Implement the smallest RHS preaggregation renderer for the Java happy-path contract. | SQL marker replay covers RHS preaggregation, join key, fixed filter, fallback alias, `count(*)`, and missing right-key groupBy fail-closed behavior. |
| P0-83 SQLite live-result parity | Completed | Execute the happy path against SQLite and compare Java snapshot result semantics. | Left-side measure is not multiplied; aggregate output matches focused SQLite oracle data. |
| P0-84 governance and metadata boundary | Completed | Add denied-source-column refusal and aggregate output lineage metadata. | Focused Python governance/metadata tests prove sanitized denied-source failure and lineage on build columns. |
| P0-85 pushdown diagnostics boundary | Completed | Add AND pushdown, OR retained diagnostics, and runtime filter fail-closed behavior aligned to Java fixture cases. | Diagnostic reason-code replay covers RHS where pushdown, RHS having pushdown, OR outer-only retention, and missing extData refusal. |
| P0-86 Java fixture gap inventory | Completed | Compare Java 9.2 aggregate acceptance evidence with the original Python 10-case fixture. | Missing governance/API/SQL behavior cases are classified with risk and next gate. |
| P0-87 governance snapshot expansion | Snapshot/replay complete; first runtime slice complete | Add Java-exported fieldAccess, system_slice, denied-source, calculated-field, and raw accessBuilder governance evidence. | Java exporter emits stable v2 case ids; Python fixture/replay is regenerated from that output; Python runtime covers aggregate output fieldAccess allow/deny and system_slice guard no-leak in the narrow SQLite path. |
| P0-88 API metadata contract | Contract ready | Freeze the V3 public `aggregateRelation` DTO key set and parent measure attributes. | Python public metadata exposes exactly the Java seven-key lineage object while internal compiler metadata can keep engine-only fields. |

## Ordering Rules

- Do not implement SQL lowering before P0-79 refusal and P0-80 guarded
  attachment exist.
- Do not add broad dialect support before SQLite SQL/result parity is stable.
- Do not expand to Odoo models before engine-neutral Java/Python parity gates
  pass.
- Do not treat aggregate relations as ordinary explicit joins.
- Do not expand product-facing behavior beyond the narrow SQLite boundary until
  external dialect, DTO exposure, and broader QueryModel stage evidence exists.

## Evidence Required From Java

The active fixture is
`tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`, exported
from Java by `JavaQueryModelAggregateJoinSnapshotTest`. The P0-79+ sequence
should continue using the v2 fixture as the default contract until Java exports
a newer stable snapshot.

Additional Java evidence should be requested only when a planned item needs
behavior that the current 19-case snapshot does not encode.

P0-86 confirms that Java 9.2 acceptance has additional aggregate relation
evidence outside the original 10-case fixture. P0-87 now owns the exported v2
governance fixture, Python replay increment, and the first runtime slice for
aggregate output fieldAccess/system_slice behavior. P0-88 owns the API metadata
DTO contract before Python public metadata exposure changes.

## Open Risks

- PostgreSQL/MySQL/TMS DB support remains follow-up after the SQLite boundary.
- Broader predicate pushdown must not drift into best-effort optimizer behavior;
  new cases need stable reason codes before exposure.
- V3 API DTO exposure for aggregate relation lineage remains separate from the
  internal `QueryBuildResult.columns` metadata proven by P0-84.
- Calculated fields over aggregate relation outputs and multi-relation QueryModel
  stages remain unsupported in the current narrow path.
- The current committed fixture covers aggregate output fieldAccess,
  system_slice guard bypass, raw accessBuilder outer-only behavior, and
  calculated-field denied-source governance as Java replay evidence. Python
  runtime now covers aggregate output fieldAccess allow/deny and system_slice
  guard no-leak, while calculated/predefined calculated behavior, raw
  accessBuilder runtime behavior, and broader governance positives remain
  follow-up.
- The exact public API metadata DTO exposure remains separate from internal
  build-column metadata.
