---
doc_purpose: Record the next Java fixture export backlog for Python QueryModel aggregate relation parity.
version: v3.8-python-alignment
priority: P0-91
status: completed
owner: python-engine
---

# P0-91 QueryModel Aggregate Java Fixture Export Backlog

Date: 2026-06-13

## Scope

P0-91 is a Python-side planning and evidence item. It does not modify the Java
snapshot exporter, regenerate fixtures, change Python runtime behavior, or touch
Odoo business models.

The purpose is to turn the Java aggregate relation evidence that is still
outside the active Python replay fixture into an ordered export request. This
keeps P0-90's fail-closed boundary intact until Java publishes a stable
snapshot for the next behavior slice.

Later status note: P0-92 exported the requested v3 fixture,
`querymodel-aggregate-join-3`, and P0-93 consumed it in Python replay. P0-94
and P0-95 implemented only the lowest-risk slices from this backlog. The
remaining P0-A items stay as fixture-only or follow-up runtime candidates.

## Worktree Guard

- Java mainline status was checked before this item and was clean at that
  moment.
- Model registry status was checked before this item and was clean at that
  moment.
- Python already had active alignment edits from the P0-87 through P0-90 lane;
  P0-91 only adds documentation/planning on top of that state.
- No commit, push, reset, cleanup, fixture regeneration, or Java exporter
  execution is part of this item.

## Inputs Read

- Java `docs/9.2.0/workitems/query-model-aggregate-join.md`
- Java `docs/9.2.0/coverage/query-model-aggregate-join-coverage-audit.md`
- Java
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/ecommerce/AggregateJoinQueryModelTest.java`
- Java
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/parity/JavaQueryModelAggregateJoinSnapshotTest.java`
- Python P0-86 through P0-90 aggregate relation workitems

## Active Snapshot Baseline

At the time P0-91 was written, the active aggregate relation snapshot lane was
`querymodel-aggregate-join-2`, exported by
`JavaQueryModelAggregateJoinSnapshotTest` and replayed by Python from
`tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`.

The v2 fixture has 19 cases:

- `aggregate-join-left-measure-not-multiplied`
- `aggregate-join-sql-shape-sqlite`
- `aggregate-join-missing-right-key-groupby-refusal`
- `aggregate-join-fixed-rhs-filter`
- `aggregate-join-runtime-extdata-filter`
- `aggregate-join-runtime-extdata-missing-refusal`
- `aggregate-join-and-pushdown-diagnostics`
- `aggregate-join-or-outer-only-diagnostics`
- `aggregate-join-denied-source-column-refusal`
- `aggregate-join-field-access-allow-output`
- `aggregate-join-field-access-deny-output-refusal`
- `aggregate-join-system-slice-guard-bypass-no-leak`
- `aggregate-join-denied-source-column-unreferenced-pass`
- `aggregate-join-calculated-field-denied-source-refusal`
- `aggregate-join-calculated-field-chain-denied-source-refusal`
- `aggregate-join-predefined-calculated-field-denied-source-refusal`
- `aggregate-join-predefined-calculated-field-allowed-exec`
- `aggregate-join-raw-sql-access-builder-outer-only`
- `aggregate-join-metadata-lineage`

Python has used that fixture plus focused SQLite regressions to close the first
narrow runtime boundary. The next fixture should therefore freeze behavior that
is either already Python-covered from Java doc/test evidence but not exported,
or currently refused by Python because Java has not supplied a replay contract.

Current baseline after P0-93 is `querymodel-aggregate-join-3` with 29 cases.
Python replay is active for the v3 fixture, and runtime implementation is
bounded to P0-94/P0-95 slices: unsafe runtime-filter refusal, null-check
outer-only predicates, public diagnostics, aggregate output `orderBy`, and
`returnTotal`.

## Export Backlog

Suggested next snapshot contract name: `querymodel-aggregate-join-3`.

| Candidate | Java Evidence | Why Python Needs It | Suggested Fixture Payload | Python Use | Priority |
| --- | --- | --- | --- | --- | --- |
| Aggregate output `orderBy` | `aggregateRelationMeasureOrderByShouldRetainProjection`; coverage audit AJ-REQ-09. | P0-92 exported and P0-93 replays the v3 case; P0-95 implements bounded aggregate-output ordering in the narrow SQLite path. | Closed for aggregate output alias ordering in the narrow SQLite path; external dialects and broader order expressions remain open. | Keep v3 replay and focused Python SQL/runtime test active. | P0-A complete |
| QueryFacade `returnTotal` | `aggregateRelationReturnTotalShouldKeepAggregateRelationQuery`; coverage audit AJ-REQ-09. | P0-92 exported and P0-93 replays the v3 case; P0-95 implements bounded total SQL execution and `totalData` filling in the narrow SQLite path. | Closed for the narrow SQLite aggregate relation path; broad QueryModel total semantics and non-SQLite dialects remain open. | Keep v3 replay and focused Python total SQL/result test active. | P0-A complete |
| Null-check output predicates | `aggregateRelationOutputNullSliceShouldStayOuterWhere` and `aggregateRelationOutputNotNullSliceShouldStayOuterWhere`. | P0-92 exported and P0-93 replays the v3 cases; P0-94 implements outer-only null checks for aggregate outputs and non-join RHS group-key outputs. | Closed for the narrow SQLite path; broader relation/dialect combinations remain open. | Keep replay plus null-check outer-only runtime diagnostics active. | P0-A complete |
| Diagnostic `debug.extra` contract | `semanticResponseShouldExposeAggregateRelationDiagnostics`, retained/refused diagnostics, and `AggregateRelationDiagnosticContractTest`. | P0-92 exported and P0-93 replays the v3 debug payload; P0-94 exposes `debug.extra.aggregateRelationDiagnostics` in validate and execute paths. | Closed for the current diagnostic key/reason-code contract in the narrow SQLite path. | Keep replay and focused response-debug assertions active. | P0-A complete |
| Composite-key aggregate relation | `tmsStyleAggregateRelationShouldPushCompositeKeyFilters`. | P0-92 exports a v3 fixture case and P0-93 replays it; Python runtime implementation remains deferred. | Replay evidence exists, but runtime support is not implemented. Do not move to Odoo/TMS models before an engine-neutral runtime slice exists. | Add a bounded SQLite composite-key runtime work item before product exposure. | P0/P1 follow-up |
| RHS dimension fixed filter | `aggregateRelationRhsFixedFilterShouldSupportRightDimensionField`. | P0-92 exports a v3 fixture case and P0-93 replays it; Python runtime implementation remains deferred. | Replay evidence exists, but dimension-path lowering is not implemented. | Add a bounded path-resolution runtime work item with fixture-driven SQL markers. | P0/P1 follow-up |
| Left joined and nested dimension keys | `aggregateRelationOnLeftKeyShouldSupportJoinedDimensionField`, `aggregateRelationOnLeftDimensionKeySliceShouldResolveJoinPath`, `aggregateRelationNestedDimensionPathOnLeftKeyShouldResolveJoinPath`. | P0-92 exports v3 fixture evidence for the first left-dimension shape and P0-93 replays it; broader nested runtime remains deferred. | Fixture-only evidence exists for part of the lane; runtime support is not implemented. | Add after neutral fixture proves shape; do not start with Odoo models. | P0/P1 follow-up |
| O615 no-column, alias, tenant guard, and join-path cases | O615 probe tests for no-column requests, explicit join aliases, tenant guard, RHS dimension `$id`, and RHS dimension filters. | These are high-value Java regressions, but too specific to infer from Python runtime tests alone. | No-columns request cases, external aliases, tenant guard no-leak assertions, expected groupBy tenant key markers, and sanitized fieldAccess output. | Freeze as fixture before Python implements broader no-column and alias behavior. | P0-A |
| Structured `accessBuilder` field-ref pushdown | `aggregateRelationAccessBuilderFieldRefShouldPushRightWhere`; raw SQL outer-only is already in v2. | P0-92 exports a v3 fixture case and P0-93 replays it; Python runtime implementation remains deferred. | Replay evidence exists, but bounded structured field-ref pushdown is not implemented. | Add replay-backed runtime support only after reviewing parser/path safety. | P0/P1 follow-up |
| Runtime filter unsafe-character refusal | `aggregateRelationRuntimeFilterShouldRejectUnsafeCharacters`. | P0-92 exports and P0-93 replays the negative security case; P0-94 implements sanitized unsafe string refusal. | Closed for simple runtime extData strings in the narrow path. | Keep replay and focused unsafe-value refusal test active. | P0-A complete |
| MySQL 5.7 explain markers | MySQL profile tests covering pushed RHS filters and EXPLAIN markers. | Python aggregate relation runtime is SQLite-only; dialect expansion needs SQL/explain evidence before implementation. | Dialect-tagged MySQL 5.7 SQL/explain markers such as index use, ref access, and expected pushed filter markers. | Plan P1/P2 dialect work; no SQLite behavior change. | P1 |
| PostgreSQL and production TMS DB evidence | Java coverage audit marks these as follow-up risks. | Java itself has not frozen these as stable acceptance evidence. | Defer until Java records stable evidence. | Track only; not a Python blocker. | P2 |

## Defer Until Contract Exists

Do not infer positive Python support for the following from broader engine
features alone:

- aggregate relation `groupBy`
- aggregate relation `having`
- post-aggregate calculations
- post slice stages
- aggregate relation `timeWindow`
- aggregate relation pivot combinations
- multi-relation aggregate join planning

P0-90 keeps these request stages fail-closed. They should only move from
refusal to implementation after Java exports aggregate-relation-specific SQL,
result, metadata, or error fixtures.

## Recommended Order

1. Keep the P0-92/P0-93 v3 neutral fixture replay active for the 29-case
   contract.
2. Treat P0-94/P0-95 as the completed low-risk runtime slice: unsafe runtime
   filter refusal, null-check outer-only diagnostics, public `debug.extra`
   diagnostics, `orderBy`, and `returnTotal`.
3. Review the replay-only v3 cases before implementing more runtime behavior:
   composite keys, structured accessBuilder field-ref pushdown, RHS dimension
   fixed filters, left/nested dimension join paths, and O615 alias/no-column
   boundaries.
4. Keep MySQL 5.7, PostgreSQL, production TMS DB, multi-relation, and broad
   QueryModel stage behavior outside the next implementation slice.

## Acceptance Criteria

- The active v2 19-case snapshot baseline is recorded.
- Java acceptance/test evidence outside v2 is classified into export
  candidates with Python usage and priority.
- P0-90 fail-closed request-stage behavior remains the active Python runtime
  boundary.
- No Java exporter, generated fixture, registry artifact, or runtime code is
  changed by this work item.

## Execution Check-In

- Status: completed as a documentation and fixture-backlog item.
- Runtime impact: none.
- Verification on 2026-06-13: `git diff --check` passed.
- No pytest was required for P0-91 because this item changed documentation
  only.
