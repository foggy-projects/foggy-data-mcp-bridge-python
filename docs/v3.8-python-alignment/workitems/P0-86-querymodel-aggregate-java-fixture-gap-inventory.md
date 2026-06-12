---
doc_purpose: Inventory Java aggregate relation evidence not yet represented in the Python snapshot lane.
version: v3.8-python-alignment
priority: P0-86
status: completed
owner: python-engine
---

# P0-86 QueryModel Aggregate Java Fixture Gap Inventory

Date: 2026-06-12

## Scope

This work item audits Java 9.2 aggregate relation acceptance evidence against
the active Python Java snapshot replay lane after P0-82 through P0-85. It does
not add runtime behavior, refresh Java fixtures, or touch Odoo business models.

The purpose is to decide which Java evidence needs a new exporter/snapshot
increment before Python broadens aggregate relation behavior beyond the narrow
SQLite boundary.

## Inputs Read

- Java `docs/9.2.0/workitems/query-model-aggregate-join.md`
- Java `docs/9.2.0/acceptance/query-model-aggregate-join-acceptance.md`
- Java `JavaQueryModelAggregateJoinSnapshotTest`
- Python `tests/fixtures/java_querymodel_aggregate_join_snapshot_contract.json`
- Python `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`
- Python `tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py`
- Python `tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py`
- Python P0-72 through P0-85 aggregate relation workitems and quality review

## Current Python Fixture Baseline

The active committed fixture has 10 Java-exported cases:

| Case | Type | Current Python Replay Purpose |
| --- | --- | --- |
| `aggregate-join-left-measure-not-multiplied` | result | SQLite live-result semantics: root-side measure is not multiplied by RHS fact rows. |
| `aggregate-join-sql-shape-sqlite` | sql | RHS preaggregation, LEFT JOIN, fixed filters, and expected SQL markers. |
| `aggregate-join-missing-right-key-groupby-refusal` | error | Missing RHS join key in aggregate groupBy fails closed. |
| `aggregate-join-fixed-rhs-filter` | sql | Fixed RHS filter is lowered into the RHS aggregate subquery. |
| `aggregate-join-runtime-extdata-filter` | sql | Runtime extData RHS filter resolves and lowers. |
| `aggregate-join-runtime-extdata-missing-refusal` | error | Missing runtime extData RHS filter value fails closed. |
| `aggregate-join-and-pushdown-diagnostics` | sql | Simple AND RHS filters push down with deterministic diagnostics. |
| `aggregate-join-or-outer-only-diagnostics` | sql | OR filters remain outer-only with deterministic diagnostics. |
| `aggregate-join-denied-source-column-refusal` | error | Referenced denied RHS source physical column fails closed. |
| `aggregate-join-metadata-lineage` | metadata | Internal aggregate output lineage exists on build columns. |

P0-82 through P0-85 use this fixture to prove the first Python runtime boundary:
carrier attachment, SQLite SQL lowering, focused live-result parity, RHS
source-column denial, internal metadata lineage, pushdown diagnostics, and
runtime extData fail-closed behavior.

## Java Evidence Not Yet In The Fixture

| Capability | Java Current Evidence | Current Python Evidence | Parity Gap | Risk | Suggested Next Gate | Recommended Verification |
| --- | --- | --- | --- | --- | --- | --- |
| Aggregate output `fieldAccess` allow | Java acceptance records aggregate relation output field access passing through the QueryModel path. | No current 10-case fixture case. Python has internal output metadata but no aggregate-specific fieldAccess replay. | Need a Java snapshot proving selected aggregate outputs remain visible when allowed. | High | P0-87 | Export a governance snapshot case and replay through Python validation/build. |
| Aggregate output `fieldAccess` deny | Java acceptance records aggregate output denial and sanitized refusal. | P0-84 covers denied RHS source physical column, not output-level fieldAccess. | Need output alias denial separate from denied source-column mapping. | High | P0-87 | Export deny case with expected error code/message markers and forbidden physical markers. |
| `system_slice` guard bypass with no field leak | Java acceptance records system slice bypassing field access without leaking guard fields. | No aggregate relation fixture case. | Need proof that governance guards merge before aggregate lowering and do not require user-visible guard fields. | High | P0-87 | Export SQL/metadata/error-free case with forbidden projection markers for guard-only fields. |
| Raw SQL `accessBuilder` outer-only | Java acceptance records raw SQL accessBuilder predicates staying outer-only. | P0-85 covers simple AND pushdown and OR retained diagnostics, not raw accessBuilder boundaries. | Need a reason-code fixture proving non-structured raw predicates are not pushed into RHS. | Medium | P0-87 or P0-89 | Export diagnostics case with outer-only marker and no RHS pushdown marker. |
| Unreferenced denied source column pass-through | Java acceptance records unrelated denied RHS source column passing. | P0-84 covers referenced denied source refusal only. | Need to distinguish denied source dependencies from unrelated denied physical columns. | Medium | P0-87 | Export pass case plus Python replay that validates/builds without leaking denied source. |
| Dynamic calculated field direct denied dependency | Java acceptance records calculated field dependency denial over aggregate relation sources. | Python aggregate relation narrow path currently rejects calculated fields over aggregate outputs as unsupported. | Need fixture to preserve fail-closed dependency behavior before allowing calculated fields. | High | P0-87 | Export sanitized refusal case; Python may initially replay as an explicit unsupported or denied dependency until implementation is split. |
| Dynamic calculated field chained denied dependency | Java acceptance records transitive calculated dependency denial. | No aggregate-specific fixture. | Need transitive dependency proof before broad calculated field support. | High | P0-87 | Export chained denial case with forbidden physical/source markers. |
| Predefined calculated field denied dependency | Java acceptance records predefined calculated field dependency denial. | No aggregate-specific fixture. | Need predefined formula dependency proof before exposing formula execution over aggregate outputs. | High | P0-87 | Export sanitized refusal case. |
| Predefined calculated field allowed execution | Java acceptance records positive predefined calculated execution. | Python aggregate relation narrow path does not yet support calculated field execution over aggregate outputs. | Positive execution is a later implementation gap; snapshot evidence should precede code changes. | High | P0-87 as evidence, P1 implementation | Export positive result case; Python can keep it documented as pending until the implementation gate opens. |
| V3 JSON metadata `aggregateRelation` contract | Java `SemanticServiceV3Test#testMetadata_Json_ShouldExposeAggregateRelationMeasure` verifies public metadata keys and measure attributes. | P0-84 exposes internal `QueryBuildResult.columns` lineage. Public DTO filtering/shape is not frozen. | Need API-level contract so Python does not leak internal-only metadata or diverge from Java keys. | High | P0-88 | Freeze key set and add Python API metadata tests before exposing DTO behavior. |
| Group-key alias request slice | Java acceptance records aggregate group-key alias request slices. | Current Python fixture has join-key/groupBy SQL markers, not request-slice alias semantics. | Need alias resolution fixture before broad request-shape support. | Medium | P0-89 | Export SQL/result case with requested group-key alias. |
| Derived relation parameter binding and explain | Java acceptance records derived relation parameter binding/explain behavior. | P0-85 covers runtime extData filters, not derived relation parameter binding/explain. | Need explicit fixture for parameter propagation through derived relation carriers. | Medium | P0-89 | Export SQL/diagnostics case with bound params and explain markers. |
| Relation-level RHS projection pruning/default measure aggregation | Java acceptance records RHS projection pruning and default measure aggregation. | Current SQL markers indirectly forbid some bad aggregate shapes, but do not prove the full pruning/default matrix. | Need dedicated SQL marker cases for pruned RHS projections and default measure behavior. | Medium | P0-89 | Export SQL-shape cases with forbidden raw RHS columns and expected aggregate expressions. |
| Query `orderBy` and `returnTotal` with aggregate relation | Java acceptance records orderBy and QueryFacade returnTotal behavior. | Python narrow aggregate relation path rejects or defers broader request options. | Need later QueryModel stage support and API contract. | High | P1 | Export result/metadata cases after API contract is stable. |
| Mixed OR and AND in/range predicate boundary | Java acceptance records mixed predicate boundaries. | P0-85 covers simple AND pushdown and OR outer-only, but not mixed OR+AND in/range cases in the fixture. | Need richer optimizer diagnostics without drifting into best-effort behavior. | Medium | P0-89 | Export diagnostics cases with stable reason codes. |
| TMS-style composite-key aggregate fixture | Java acceptance records local TMS-style composite-key evidence. | Python avoids Odoo/TMS business models in P0 and has no engine-neutral composite aggregate fixture. | Need neutral composite-key evidence before touching business models. | High | P1 | Export engine-neutral composite-key fixture, then add Python replay. |
| MySQL 5.7 live aggregate relation evidence | Java acceptance records MySQL 5.7 live evidence. | Python aggregate relation runtime is SQLite-only. | External dialect parity remains open after SQLite closure. | High | P1 | Add dialect SQL/result fixture only after governance/API contract gates. |
| PostgreSQL and production TMS DB evidence | Java acceptance itself marks these as follow-up risks. | No Python evidence. | Not a Python parity target until Java has stable evidence. | Medium | P2 | Track as future cross-dialect/live DB evidence, not a P0 blocker. |

## Recommended Split

1. P0-87 should expand Java-exported aggregate governance evidence before Python
   broadens behavior. The first target is field access, system slice, denied
   source-column dependency, and calculated-field dependency governance.
2. P0-88 should freeze the public API metadata contract before exposing Python
   aggregate relation lineage through V3 metadata DTOs.
3. P0-89 should be reserved for SQL behavior expansion that is not strictly
   governance or API metadata: group-key alias slices, derived relation
   parameter binding, pruning/default aggregation, and richer predicate
   diagnostics.

## Acceptance Criteria

- The current 10-case fixture remains the active P0-82 through P0-85 replay
  baseline.
- Java 9.2 acceptance evidence not represented in that fixture is listed with a
  suggested owner gate.
- No Java worktree code, registry artifacts, generated Odoo models, or Python
  runtime behavior are changed by this inventory item.
- P0-87 and P0-88 can start from this inventory without re-reading the full
  Java acceptance document.

## Execution Check-In

- Status: completed as a documentation and planning item.
- Implementation impact: none.
- Verification on 2026-06-12:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `10 passed in 0.05s`.
- `git diff --check` passed.
