---
doc_purpose: Plan the P0-79+ sequence for Python-Java QueryModel aggregate join alignment.
version: v3.8-python-alignment
priority: P0-79+
status: planned
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

## Planned Sequence

| Item | Status | Purpose | Acceptance Gate |
| --- | --- | --- | --- |
| P0-79 runtime/compiler refusal boundary | Completed | Refuse any model carrying `aggregate_relations` before SQL generation until lowering exists. | Focused runtime/compiler refusal test plus existing loader and Java snapshot replay green. |
| P0-80 loader attachment behind refusal | Completed | Allow parsed aggregate carriers to attach to a QueryModel only in a controlled path that still refuses before SQL/runtime. | Loader can produce an alias model with `aggregate_relations` in a clearly guarded path; runtime still fails closed. |
| P0-81 minimal SQL-shape design for SQLite happy path | Completed | Define Python lowering shape for RHS grouped subquery and LEFT JOIN based on the committed Java fixture. | Design doc plus expected SQL markers; no broad runtime exposure. |
| P0-82 SQLite SQL lowering skeleton | Planned | Implement the smallest RHS preaggregation renderer for the Java happy-path contract. | SQL marker replay for RHS preaggregation, join key, fixed filter, and non-multiplication shape. |
| P0-83 SQLite live-result parity | Planned | Execute the happy path against SQLite and compare Java snapshot result semantics. | Left-side measure is not multiplied; aggregate output matches independent oracle SQL. |
| P0-84 governance and metadata boundary | Planned | Add denied-column/calculated-field dependency refusal and V3 aggregate lineage surface. | Java governance/metadata cases replay or focused Python equivalents, with sanitized errors. |
| P0-85 pushdown diagnostics boundary | Planned | Add AND pushdown and OR/mixed retained/refused diagnostics aligned to Java fixture cases. | Diagnostic reason-code replay against the Java aggregate snapshot. |

## Ordering Rules

- Do not implement SQL lowering before P0-79 refusal and P0-80 guarded
  attachment exist.
- Do not add broad dialect support before SQLite SQL/result parity is stable.
- Do not expand to Odoo models before engine-neutral Java/Python parity gates
  pass.
- Do not treat aggregate relations as ordinary explicit joins.
- Do not expose product-facing behavior until SQL, governance, metadata, and
  diagnostics have explicit evidence.

## Evidence Required From Java

The active fixture is
`tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`, exported
from Java by `JavaQueryModelAggregateJoinSnapshotTest`. The P0-79+ sequence
should continue using that fixture as the default contract until Java exports a
newer stable snapshot.

Additional Java evidence should be requested only when a planned item needs
behavior that the current 10-case snapshot does not encode.

## Open Risks

- Aggregate relation output ownership must not bypass denied-column or
  calculated-field dependency checks.
- Runtime filters must stay inside the RHS relation only when Java-compatible
  binding and missing-value behavior are proven.
- Pushdown diagnostics must not drift into best-effort optimizer behavior; they
  need stable reason codes.
- PostgreSQL/MySQL support should remain follow-up after SQLite closes.
