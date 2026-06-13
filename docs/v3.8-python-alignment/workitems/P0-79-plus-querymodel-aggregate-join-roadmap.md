---
doc_purpose: Plan the P0-79+ sequence for Python-Java QueryModel aggregate join alignment.
version: v3.8-python-alignment
priority: P0-79+
status: completed-through-P0-95
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
  the narrow SQLite aggregate relation path, and an explicit runtime assertion
  now proves unreferenced RHS denied-source pass-through. Dynamic calculated
  direct/chain denied-source dependencies also fail closed through the same
  aggregate governance boundary, and predefined calculated dependency denial
  plus positive predefined calculated execution are now covered by the narrow
  runtime path. Raw SQL accessBuilder predicates now stay root/outer-only in
  the Python SQLite runtime path and are not pushed into the RHS aggregate
  subquery.
- P0-88 freezes and implements the public API metadata contract for aggregate
  relation lineage through `get_metadata_v3(...)`: aggregate output fields are
  exposed as normal measures with exactly the Java seven-key
  `aggregateRelation` object, while internal compiler lineage keeps
  engine-only semantic-unit metadata.
- P0-89 starts the next SQL behavior expansion lane and completes four
  low-risk regression/implementation slices.
  Python now explicitly proves that a left request alias can push into the
  mapped RHS aggregate group key, that fixed RHS filters, pushed RHS WHERE,
  pushed aggregate HAVING, outer predicates, SQLite EXPLAIN, and live execution
  share deterministic placeholder params, and that structured RHS projection
  pruning keeps only referenced aggregate outputs while raw SQL accessBuilder
  keeps full projection. It also proves mixed OR join-key/measure predicates
  remain outer-only with retained diagnostics, while explicit AND wrapper
  `in`/range predicates keep RHS WHERE/HAVING pushdown.
- P0-90 hardens the fail-closed boundary for broader aggregate relation request
  stages that do not yet have Java snapshot/result fixtures. `groupBy`,
  `having`, `orderBy`, `returnTotal`, post stages, `timeWindow`, and the
  internal aggregate/pivot combination now have focused refusal coverage.
- P0-91 records the next Java aggregate relation fixture export backlog. It
  keeps the active v2 replay lane unchanged while classifying the candidate v3
  fixture cases needed before Python broadens behavior beyond the current
  fail-closed request-stage boundary.
- P0-92 exports the v3 Java aggregate relation fixture with 29 cases.
- P0-93 promotes the v3 fixture into Python replay.
- P0-94 implements the first v3 low-risk runtime slice: unsafe runtime-filter
  refusal, null-check outer-only predicates, public diagnostics, and aggregate
  relation group-key schema validation.
- P0-95 opens bounded aggregate-output `orderBy` and `returnTotal` support for
  the narrow SQLite aggregate relation path, while keeping `groupBy`, `having`,
  post stages, `timeWindow`, pivot combinations, external dialects,
  multi-relation planning, and Odoo business models out of scope.

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
| P0-87 governance snapshot expansion | Snapshot/replay complete; focused runtime governance slice complete | Add Java-exported fieldAccess, system_slice, denied-source, calculated-field, and raw accessBuilder governance evidence. | Java exporter emits stable v2 case ids; Python fixture/replay is regenerated from that output; Python runtime covers aggregate output fieldAccess allow/deny, system_slice guard no-leak, unreferenced RHS denied-source pass-through, dynamic calculated direct/chain denied-source refusal, predefined calculated dependency refusal, positive predefined calculated execution, and raw accessBuilder outer-only behavior in the narrow SQLite path. |
| P0-88 API metadata contract | Implemented | Freeze and expose the V3 public `aggregateRelation` DTO key set and parent measure attributes. | Python public metadata exposes exactly the Java seven-key lineage object while internal compiler metadata keeps engine-only fields; RHS denied source columns hide the corresponding aggregate output metadata. |
| P0-89 SQL behavior expansion | Completed | Expand non-governance aggregate relation SQL behavior with fixture-backed, low-risk slices. | Current slices prove group-key alias request slice pushdown/live SQLite result, derived relation parameter/explain behavior, RHS projection pruning/default aggregation with raw SQL accessBuilder fallback, mixed OR outer-only diagnostics, and AND wrapper `in`/range RHS pushdown. |
| P0-90 request-stage refusal hardening | Completed; partly superseded by P0-95 | Keep broader aggregate relation request stages fail-closed until Java fixtures define positive semantics. | Focused runtime refusal coverage registers RHS and proves unsupported stages do not generate SQL or leak physical table names. P0-95 later supersedes the `orderBy` and `returnTotal` refusal for the narrow SQLite path. |
| P0-91 Java fixture export backlog | Completed | Convert Java aggregate relation evidence outside the v2 snapshot into an ordered export request. | Candidate v3 fixture cases are classified by Java evidence, Python need, suggested payload, Python use, and priority without changing exporter/runtime behavior. |
| P0-92 v3 Java fixture export | Completed | Export the next aggregate relation Java fixture before broadening Python runtime behavior. | Java exporter emits `querymodel-aggregate-join-3` with 29 cases. |
| P0-93 v3 Python replay | Completed | Promote the v3 Java fixture into the Python manifest and replay lane. | Python replay validates the 29-case contract, including diagnostics, `orderBy`, `returnTotal`, `totalSql`, `totalData`, and sanitized error markers. |
| P0-94 low-risk runtime slices | Completed | Implement the safest v3 runtime slices without touching Odoo, external dialects, or multi-relation planning. | Focused runtime tests cover unsafe runtime-filter refusal, null-check outer-only behavior, public diagnostics, and group-key schema validation. |
| P0-95 orderBy / returnTotal gate | Completed | Open two fixture-backed request stages inside the narrow SQLite aggregate relation path. | Focused runtime/refusal tests cover aggregate-output `orderBy`, total SQL generation, execute-mode `total` / `totalData`, and continued refusal for unsupported stages. |

## Ordering Rules

- Do not implement SQL lowering before P0-79 refusal and P0-80 guarded
  attachment exist.
- Do not add broad dialect support before SQLite SQL/result parity is stable.
- Do not expand to Odoo models before engine-neutral Java/Python parity gates
  pass.
- Do not treat aggregate relations as ordinary explicit joins.
- Do not expand product-facing behavior beyond the narrow SQLite boundary until
  external dialect and broader QueryModel stage evidence exists.

## Evidence Required From Java

The active fixture is
`tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`, exported
from Java by `JavaQueryModelAggregateJoinSnapshotTest`. After P0-92/P0-93, the
current active contract is `querymodel-aggregate-join-3` with 29 cases.

Additional Java evidence should be requested only when a planned item needs
behavior that the current v3 snapshot does not encode.

P0-86 confirms that Java 9.2 acceptance has additional aggregate relation
evidence outside the original 10-case fixture. P0-87 now owns the exported v2
governance fixture, Python replay increment, and the first runtime slices for
aggregate output fieldAccess/system_slice, unreferenced denied-source behavior,
dynamic calculated direct/chain denial, predefined calculated dependency
denial, positive predefined calculated execution, and raw accessBuilder
outer-only behavior. P0-88 implements the API metadata DTO contract through
Python public V3 metadata. P0-89 locks group-key alias request-slice pushdown
and derived relation parameter/explain behavior with Python SQLite regressions,
then adds structured RHS projection pruning/default aggregation with raw SQL
accessBuilder fallback and mixed predicate boundaries based on current Java
doc/test evidence. P0-90 records the broader request-stage fail-closed boundary.

P0-91 turns the remaining Java acceptance/test evidence into a candidate
`querymodel-aggregate-join-3` export backlog. P0-92 exports that v3 fixture, and
P0-93 promotes it into Python replay. P0-94/P0-95 implement only the lowest-risk
v3 runtime slices: unsafe runtime filter refusal, null-check outer-only
diagnostics, public diagnostic `debug.extra`, aggregate output `orderBy`, and
`returnTotal`. Composite keys, RHS dimension fixed filters, left/nested
dimension keys, O615 alias/no-column boundaries, and structured accessBuilder
field-ref pushdown remain replay-only or follow-up runtime candidates. MySQL
5.7 explain markers and PostgreSQL/production TMS DB evidence remain later
dialect gates.

## Open Risks

- PostgreSQL/MySQL/TMS DB support remains follow-up after the SQLite boundary.
- Broader predicate pushdown must not drift into best-effort optimizer behavior;
  P0-89 covers the current mixed OR / AND in-range boundary, and any next cases
  need stable reason codes before exposure.
- Multi-relation and broader QueryModel request stages remain unsupported in
  the current narrow path. P0-90 makes that boundary explicit for registered
  RHS aggregate relation requests, and P0-95 only opens bounded `orderBy` and
  `returnTotal`.
- The current committed fixture covers aggregate output fieldAccess,
  system_slice guard bypass, raw accessBuilder outer-only behavior, and
  calculated-field denied-source governance as Java replay evidence. Python
  runtime now covers aggregate output fieldAccess allow/deny, system_slice
  guard no-leak, unreferenced RHS denied-source pass-through, and dynamic
  calculated direct/chain denied-source refusal plus predefined calculated
  dependency refusal plus positive predefined calculated execution plus raw
  accessBuilder outer-only behavior, while broader governance positives remain
  follow-up.
- Public V3 API metadata now exposes the seven-key aggregate relation lineage,
  but multi-model field-name collisions and richer metadata shapes still need
  dedicated follow-up evidence before broad product exposure.
- P0-89 group-key alias pushdown, derived relation parameter/explain behavior,
  structured RHS projection pruning/default aggregation, and mixed predicate
  boundaries are covered by Python regression evidence plus current Java
  doc/test evidence; future Java fixtures should still freeze the cross-engine
  contract before broad request-shape exposure.
- P0-92/P0-93 make the v3 fixture the active runtime contract source, but not
  every v3 case is implemented in Python. Replay-only cases must remain clearly
  separated from runtime support.
