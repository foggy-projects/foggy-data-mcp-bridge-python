---
doc_role: workitem
doc_purpose: Freeze the Python landing-point audit for Java 9.2 QueryModel aggregate join before Python implementation.
version: v3.8-python-alignment
priority: P0
status: docs-complete
created_at: 2026-06-11
updated_at: 2026-06-11
source_type: parity-gap-audit
owner_repo: foggy-data-mcp-bridge-python
owner_module: dataset_model
java_reference_repo: foggy-data-mcp-bridge-wt-dev-compose
java_reference_version: 9.2.0
---

# P0-72 QueryModel Aggregate Join Python Gap Audit

## Purpose

This work item records the Python parity gap for Java 9.2 QueryModel aggregate
join and freezes the recommended Python landing points before implementation.
It is intentionally a planning/audit cut: no production Python aggregate-join
code is introduced here.

## Scope

- Read current Java aggregate-join docs and implementation evidence.
- Compare Python QueryModel, ordinary explicit join, metadata, governance, and
  SQL-generation landing points.
- Define the first safe follow-up steps for neutral snapshot verification.
- Keep Odoo business models and generated registry content out of this line.

## Non-Scope

- No Python production aggregate-join implementation.
- No Java or registry source changes.
- No Odoo model refresh.
- No public MCP schema change for aggregate join.

## Java Current State

Java 9.2 QueryModel aggregate join is accepted with documented risks. The Java
contract lets the right-hand side relation aggregate before a LEFT JOIN so a
1:N detail table does not multiply main-side measures.

Current Java capability summary:

| Area | Java state |
| --- | --- |
| Contract | Same datasource, LEFT JOIN first, structured aggregate relation rather than free SQL/CTE. |
| DSL | Both `leftJoinAggregate(...)` compatibility API and aggregate-relation-first DSL are supported. |
| RHS aggregation | Right relation applies filters before `GROUP BY`, then exposes aggregate outputs for the outer QueryModel. |
| Aggregate functions | Workitem scope started with `SUM`, `COUNT`, `MIN`, `MAX`; implementation evidence also covers `avg` and `countDistinct` in the relation DSL. |
| Grain validation | RHS `groupBy` must cover right-side join-key fields; invalid grain fails closed. |
| Runtime filters | RHS fixed filters and function-valued runtime filters from request `extData` render inside the derived aggregate relation; missing runtime values fail closed. |
| Request pushdown | AND-only safe request slices on join keys/group keys and aggregate measures may be duplicated to RHS `WHERE`/`HAVING`; OR and mixed complex predicates remain outer-only. |
| Projection pruning | Structured references prune unused RHS aggregate relation measures; raw SQL accessBuilder predicates force conservative full RHS projection. |
| Governance | `fieldAccess`, `system_slice`, source physical `deniedColumns`, dynamic calculatedFields, chained calculatedFields, and predefined QM calculated fields are covered for aggregate relation outputs. |
| Metadata | V3 JSON metadata exposes aggregate relation lineage including aggregation, source caption/measure/alias/expression/column, aggregate expression, and semantic scale/unit inheritance in the current implementation. |
| Diagnostics | Latest Java ahead commit exposes aggregate relation pushdown diagnostics with pushed/retained/refused decisions and reason codes. |
| Evidence | SQLite and MySQL 5.7 real execution/explain evidence exists, including a local TMS-style composite-key fixture. PostgreSQL and production TMS DB evidence remain follow-up risks. |

The Java repo was read-only during this audit. At audit time it was ahead of
`origin/main` by commit `84000c81 feat: expose aggregate relation pushdown
diagnostics`.

## Python Current State

Python has useful adjacent primitives, but no QueryModel aggregate join
implementation.

Current Python landing points:

| Area | Python state |
| --- | --- |
| Ordinary explicit joins | `ExplicitJoinDef` / `ExplicitJoinConditionDef` and loader `_build_explicit_joins(...)` support QM-declared ordinary joins between registered models. |
| Field ownership | `field_model_map`, `model_alias_map`, `model_table_map`, and `model_schema_map` let a QM alias model resolve fields from joined source models. |
| SQL generation | `SemanticQueryService` adds ordinary explicit joins when referenced fields are selected, filtered, grouped, ordered, or used by timeWindow. |
| Compose query | The compose engine supports base/derived/union/join SQL and dialect fallback, but that is a QueryPlan surface, not QueryModel aggregate relation exposure. |
| Governance | QueryModel denied columns, visible fields, calculatedFields dependency checks, Pivot/domain transport governance, and sanitized errors have active Java snapshot replay. |
| Metadata | `get_metadata_v3(...)` exposes models/fields and denied-column trimming, but has no `aggregateRelation` lineage object. |
| Diagnostics | There is no aggregate relation pushdown diagnostic carrier. |
| Fixtures | No Java aggregate-join neutral snapshot or Python replay harness exists yet. |

Important distinction: Python ordinary explicit join is not a safe substitute
for aggregate join. Extending it directly would still join detail rows before
final aggregation and could reintroduce main-side measure multiplication.

## Gap Matrix

| Capability | Java current status | Python current status | Parity gap | Risk | Suggested priority | Recommended verification |
| --- | --- | --- | --- | --- | --- | --- |
| DSL/model contract | Java supports `leftJoinAggregate(...)` and aggregate-relation-first DSL with structured relation semantics. | No aggregate relation model, parser contract, or Python authoring API. | Full contract gap. | High | P1 design, P2 implementation | Java neutral snapshot should include model declaration shape, normalized semantic contract, and refusal cases before Python parser work. |
| RHS preaggregation SQL lowering | Java lowers RHS to a structured derived aggregate relation before LEFT JOIN. | Ordinary explicit joins render physical right table joins directly. Compose derived queries exist separately. | Full lowering gap; ordinary join path cannot be reused as-is. | High | P2 | Golden SQL shape plus SQLite live-result fixture proving left-side measure is not multiplied. |
| Join key and groupBy validation | Java requires RHS `groupBy` to cover right join keys and rejects invalid grain. | No aggregate join declaration, so no grain validator. | Full validator gap. | High | P1/P2 | Fail-closed fixture: missing right join key in RHS groupBy must produce stable structured error. |
| Fixed and runtime RHS filters | Java renders fixed filters and `extData` runtime values inside RHS relation; missing values fail closed. | Python request context and slices exist, but no RHS aggregate relation filter channel. | Full runtime-filter gap. | High | P2 | Snapshot with fixed filter, extData parameter, generated params, and missing-runtime-value refusal. |
| Safe request pushdown | Java duplicates safe AND `in`/range/equality filters to RHS `WHERE`/`HAVING`; OR/mixed/raw SQL stay outer-only. | Python has no aggregate relation output classification, so cannot decide pushdown target. | Full pushdown matrix gap. | High | P2 | Snapshot diagnostics for pushed, retained, and refused predicates; assert SQL and reason codes. |
| Projection pruning | Java prunes unreferenced aggregate outputs for structured requests and keeps full RHS projection for raw SQL boundaries. | Python has selected column logic but no RHS aggregate output dependency graph. | Full pruning gap. | Medium | P2 | SQL shape fixture checking referenced vs unreferenced RHS measures. |
| `orderBy` and `returnTotal` | Java keeps RHS projection available for aggregate output orderBy and preserves aggregate relation in QueryFacade totals. | Python has orderBy/returnTotal for ordinary query paths, not aggregate relation outputs. | Feature-specific gap. | High | P2 | Result fixture with aggregate output orderBy and total SQL/result parity. |
| `fieldAccess` and `system_slice` | Java covers allow/deny on aggregate relation output and system-slice guard bypass without leaking guard fields. | Python governance covers ordinary QueryModel fields and calculatedFields, but no aggregate output owner/source mapping. | Aggregate-governance gap. | High | P2 | Governance snapshot: allowed output, denied output, system guard hidden from returned columns. |
| Source physical `deniedColumns` | Java maps aggregate outputs back to RHS source physical columns and propagates to dynamic/chained/predefined calculated fields. | Python deniedColumns maps ordinary fields and calculatedFields dependencies, but lacks aggregate output source lineage. | Security/correctness gap. | High | P2 | Deny RHS source column and assert direct aggregate output plus dependent calculated fields fail closed. |
| Metadata V3 lineage | Java exports structured `aggregateRelation` lineage keys and inherited metadata. | Python V3 metadata has no aggregate relation object. | Metadata contract gap. | Medium | P1/P2 | JSON fixture for aggregate field metadata including source column/expression/aggregation and semantic scale/unit. |
| Diagnostics | Java ahead commit adds aggregate pushdown diagnostics. | No diagnostic type or response surface. | Observability gap; needed before confident parity debugging. | Medium | P1/P2 | Snapshot diagnostics object for pushed/retained/refused predicate decisions. |
| Live DB evidence | Java has SQLite and MySQL 5.7 evidence; PostgreSQL/TMS production remains follow-up. | Python has no aggregate join live DB evidence. | Full evidence gap. | High | P2 | Start with SQLite live-result; later MySQL/Postgres only after SQL contract stabilizes. |
| Java neutral snapshot readiness | Java tests exist, but no Python-owned neutral aggregate-join fixture is committed. | Python snapshot manifest has no aggregate-join cases. | Harness/input gap before implementation. | Medium | P0/P1 | Export model-neutral JSON with declaration, request, SQL markers, params, rows, metadata, diagnostics, and refusal cases. |

## Recommended Python Landing Points

Do not implement aggregate join by bolting aggregation into the existing
ordinary explicit join renderer. The Python implementation should introduce a
separate aggregate relation carrier so grain, source physical lineage,
projection pruning, diagnostics, and pushdown decisions stay explicit.

Proposed future code touchpoints:

| Area | Likely Python files/modules |
| --- | --- |
| Model definitions | `src/foggy/dataset_model/impl/model/__init__.py` for aggregate relation def/output metadata. |
| Loader parsing | `src/foggy/dataset_model/impl/loader/__init__.py` for QM aggregate relation declarations and validation. |
| SQL lowering | `src/foggy/dataset_model/semantic/service.py` or a helper module to render RHS derived aggregate relation and join it. |
| Governance lineage | Existing denied-column and calculatedFields dependency checks in semantic service. |
| Metadata | `SemanticQueryService.get_metadata_v3(...)` aggregateRelation field metadata. |
| Diagnostics | New lightweight Python diagnostic value object or structured dict returned through snapshot/test hooks first. |
| Tests | `tests/integration/` Java snapshot parity and `tests/test_dataset_model/` focused SQL/governance/live SQLite tests. |

## First Implementation Recommendation

First phase should stay evidence-first and low-risk:

1. **P0-73: Java aggregate-join neutral snapshot contract**
   - Define the fixture envelope Python needs from Java.
   - Required cases: happy SQL/result, left measure non-multiplication,
     missing groupBy join key refusal, fixed filter, runtime extData filter,
     safe AND pushdown, OR outer-only, deniedColumns, metadata lineage, and
     diagnostics.
   - Output should be model-neutral, not Odoo/TMS-specific.

2. **P0-74: Python aggregate-join fixture manifest/replay skeleton**
   - Add manifest checks and explicit skipped/xfail markers for absent Java
     aggregate-join snapshots.
   - Keep production behavior unchanged.
   - Make the gap visible in the same parity harness style used by compose,
     governance, timeWindow, pivot, and domain transport.

3. **P1: Python contract parser and fail-closed validation**
   - Add only schema/validation and stable structured refusal behavior first.
   - Do not render executable SQL until the refusal matrix and metadata shape
     are pinned.

4. **P2: Python SQL lowering and governance parity**
   - Implement RHS derived aggregate relation, source physical lineage,
     projection pruning, safe pushdown, diagnostics, metadata, and SQLite
     live-result evidence.

## Acceptance for This Workitem

- Java aggregate-join capability and risks are summarized from current docs.
- Python adjacent capabilities and missing aggregate-specific pieces are
  identified.
- A gap matrix exists with risk, priority, and verification approach.
- Follow-up work is split into snapshot contract, Python harness, validation,
  and implementation stages.
- No Java/registry code or generated Odoo content is changed.

