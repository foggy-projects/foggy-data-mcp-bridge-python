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

Later status note: P0-87 promoted the fixture to v2, P0-92/P0-93 promoted it
again to the v3 29-case contract, and P0-94/P0-95 implemented the lowest-risk
v3 runtime slices. This inventory remains the historical gap audit after
P0-82 through P0-85; current status for v3-backed items is summarized in the
P0-91 follow-up note below.

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
| V3 JSON metadata `aggregateRelation` contract | Java `SemanticServiceV3Test#testMetadata_Json_ShouldExposeAggregateRelationMeasure` verifies public metadata keys and measure attributes. | P0-84 exposes internal `QueryBuildResult.columns` lineage; P0-88 now exposes public V3 metadata with exactly the Java seven-key `aggregateRelation` object while filtering internal-only metadata. | Core API-level DTO gap is closed for the narrow aggregate relation boundary; remaining risk is broader multi-model/multi-relation metadata shape evidence. | Medium | Closed by P0-88 | Keep the public metadata test and fixture-backed seven-key assertion active; add broader cases only when Java exports stable multi-relation metadata evidence. |
| Group-key alias request slice | Java acceptance records aggregate group-key alias request slices. | P0-89 adds a Python SQLite regression proving a request slice on a left alias pushes to the mapped RHS group key and returns the expected aggregate row. | Runtime behavior is now covered in Python, but a Java-exported SQL/result case is still needed before treating it as a cross-engine frozen contract. | Medium | P0-89 first slice complete; future Java fixture | Export SQL/result case with requested group-key alias. |
| Derived relation parameter binding and explain | Java acceptance records derived relation parameter binding/explain behavior. | P0-89 adds a Python SQLite regression proving fixed RHS filters, pushed RHS WHERE, pushed aggregate HAVING, outer predicates, and `EXPLAIN QUERY PLAN` all use the same deterministic placeholder params. | Runtime behavior is now covered in Python from Java doc/test evidence, but a Java-exported SQL/diagnostics fixture is still needed before treating it as a frozen cross-engine contract. | Medium | P0-89 second slice complete; future Java fixture | Export SQL/diagnostics case with bound params and explain markers. |
| Relation-level RHS projection pruning/default measure aggregation | Java acceptance records RHS projection pruning and default measure aggregation, including raw SQL accessBuilder disabling pruning. | P0-89 now adds Python runtime pruning for structured requests, keeps explicit default aggregate expressions, omits unreferenced RHS measures, and preserves full RHS projection for raw SQL accessBuilder. | Runtime behavior is now covered in Python from Java doc/test evidence, but a Java-exported SQL-shape case is still needed before treating the broader pruning matrix as frozen. | Medium | P0-89 third slice complete; future Java fixture | Export SQL-shape cases with forbidden raw RHS columns, expected aggregate expressions, and raw-SQL full-projection fallback. |
| Query `orderBy` and `returnTotal` with aggregate relation | Java acceptance records orderBy and QueryFacade returnTotal behavior. | P0-92/P0-93 later export and replay v3 fixture cases; P0-95 implements bounded support for aggregate output `orderBy` and `returnTotal` in the narrow SQLite path. | Closed for the bounded SQLite path; broad order expressions, total semantics outside this path, and external dialects remain open. | Medium | P0-95 complete; later dialect/broader-stage follow-up | Keep v3 replay plus focused Python order/total SQL and result tests active. |
| Null-check aggregate output predicates | Java acceptance records RHS aggregate output `is null` / `is not null` staying outer-only. | Python has mixed OR/AND predicate diagnostics, but no exported null-check aggregate relation replay. | Need a stable fixture before Python treats null checks as a frozen optimizer boundary. | Medium | P0-A fixture request | Export SQL/diagnostics cases proving null checks stay on the outer aggregate output alias and do not push into RHS WHERE/HAVING. |
| Public diagnostic `debug.extra` payload | Java acceptance and diagnostic contract tests expose aggregate relation diagnostics through semantic debug metadata. | Python has internal diagnostic assertions but no shared public debug payload contract. | Need key/reason-code evidence before exposing or asserting public response diagnostics. | Medium | P0-A fixture request | Export response metadata/debug payload with stable diagnostic keys and reason codes. |
| RHS dimension and left/nested dimension path resolution | Java acceptance records RHS dimension fixed filters, left joined dimension keys, and nested dimension path join-key resolution. | Python has simple fixed RHS filters and group-key alias pushdown, but not exported dimension path aggregate relation replay. | Dimension path lowering is higher risk than scalar key/filter support and should be fixture-led. | High | P0-A fixture request | Export SQL/result markers for RHS dimension joins, left/nested key path aliases, and request-slice join path resolution. |
| O615 no-column / alias / tenant guard regressions | Java acceptance records O615 no-column requests, explicit join aliases, tenant guard no-leak, RHS dimension `$id`, and RHS dimension filters. | Python has no aggregate-specific replay for these high-regression alias/no-column boundaries. | Need fixture evidence before implementing or claiming parity for no-column and tenant-guard aggregate relation cases. | High | P0-A fixture request | Export no-column, alias, tenant guard, and sanitized fieldAccess cases with forbidden leak markers. |
| Structured `accessBuilder` field-ref pushdown | Java acceptance records structured accessBuilder field refs pushing into RHS WHERE, while raw SQL remains outer-only. | P0-87 covers raw SQL accessBuilder outer-only; the positive structured field-ref half is not exported. | Need paired positive fixture evidence before broadening accessBuilder pushdown. | Medium | P0-A fixture request | Export SQL/diagnostics case with structured field-ref RHS pushdown and stable markers. |
| Runtime filter unsafe-character refusal | Java acceptance records unsafe runtime filter value rejection. | Python covers missing runtime extData fail-closed, not unsafe-value rejection as a fixture replay. | Security-sensitive negative behavior should be exported before runtime changes. | Medium | P0-A fixture request | Export sanitized error case with forbidden raw unsafe marker leakage. |
| Mixed OR and AND in/range predicate boundary | Java acceptance records mixed predicate boundaries: mixed OR join-key/measure predicates stay outer-only, while AND `in`/range predicates push safely to RHS WHERE/HAVING and remain outer. | P0-89 now adds Python SQLite regressions proving mixed OR outer-only rendering/retained diagnostics and explicit AND wrapper `in`/range RHS pushdown diagnostics. | Runtime behavior is now covered in Python from Java doc/test evidence, but a Java-exported diagnostics case is still needed before treating it as a frozen cross-engine contract. | Medium | P0-89 complete; future Java fixture | Export diagnostics cases with stable reason codes for mixed OR retained entries and AND `in`/range pushed entries. |
| TMS-style composite-key aggregate fixture | Java acceptance records local TMS-style composite-key evidence. | Python avoids Odoo/TMS business models in P0 and has no engine-neutral composite aggregate fixture. | Need neutral composite-key evidence before touching business models. | High | P1 | Export engine-neutral composite-key fixture, then add Python replay. |
| MySQL 5.7 live aggregate relation evidence | Java acceptance records MySQL 5.7 live evidence. | Python aggregate relation runtime is SQLite-only. | External dialect parity remains open after SQLite closure. | High | P1 | Add dialect SQL/result fixture only after governance/API contract gates. |
| PostgreSQL and production TMS DB evidence | Java acceptance itself marks these as follow-up risks. | No Python evidence. | Not a Python parity target until Java has stable evidence. | Medium | P2 | Track as future cross-dialect/live DB evidence, not a P0 blocker. |

## Recommended Split

1. P0-87 should expand Java-exported aggregate governance evidence before Python
   broadens behavior. The first target is field access, system slice, denied
   source-column dependency, and calculated-field dependency governance.
2. P0-88 closes the public API metadata contract for the narrow V3 metadata
   DTO; broader metadata shapes should wait for new Java fixture evidence.
3. P0-89 should be reserved for SQL behavior expansion that is not strictly
   governance or API metadata. Its group-key alias request-slice, derived
   relation parameter/explain, RHS projection pruning/default aggregation, and
   mixed OR / AND in-range predicate regressions are complete in Python; Java
   fixture evidence is still recommended before broad contract freeze.
4. P0-91 records the next Java fixture export backlog. P0-92/P0-93 later make
   `querymodel-aggregate-join-3` the active 29-case replay lane, and
   P0-94/P0-95 close only the low-risk runtime subset. Replay-only v3 cases
   still need separate runtime work items before positive dimension path,
   structured accessBuilder, O615, or dialect behavior expands.

## P0-91+ Follow-Up Note

P0-86 started from the original 10-case fixture baseline and identified missing
Java evidence. P0-87 later promoted the active snapshot to the 19-case
`querymodel-aggregate-join-2` governance fixture. P0-91 recorded the next
candidate export set, P0-92 exported `querymodel-aggregate-join-3`, and P0-93
activated Python replay for the 29-case v3 fixture.

P0-94/P0-95 close the low-risk runtime items for unsafe runtime-filter refusal,
null-check outer-only predicates, public diagnostics, aggregate output
`orderBy`, and `returnTotal` in the narrow SQLite aggregate relation path.
Composite keys, structured accessBuilder field-ref pushdown, RHS dimension
fixed filters, left/nested dimension keys, O615 alias/no-column boundaries,
external dialects, and production TMS DB evidence remain follow-up gaps.

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
