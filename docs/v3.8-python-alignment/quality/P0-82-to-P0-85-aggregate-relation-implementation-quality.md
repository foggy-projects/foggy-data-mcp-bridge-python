---
quality_scope: feature
quality_mode: pre-coverage-audit
version: v3.8-python-alignment
target: P0-82-through-P0-85-querymodel-aggregate-relation-sqlite-boundary
status: reviewed
decision: ready-with-risks
reviewed_by: codex
reviewed_at: 2026-06-12
follow_up_required: yes
---

# Implementation Quality Gate

## Background

P0-82 through P0-85 move Python QueryModel aggregate relation support from
runtime refusal only to a narrow SQLite parity boundary. The implementation is
intentionally limited to Java-fixture-backed aggregate relation SQL shape, live
SQLite result parity, aggregate output metadata, denied source-column
governance, pushdown diagnostics, and runtime filter fail-closed behavior.

## Check Basis

- Workitems:
  - `workitems/P0-82-querymodel-aggregate-sqlite-lowering-skeleton.md`
  - `workitems/P0-83-querymodel-aggregate-sqlite-live-result-parity.md`
  - `workitems/P0-84-querymodel-aggregate-governance-metadata-boundary.md`
  - `workitems/P0-85-querymodel-aggregate-pushdown-diagnostics-boundary.md`
- Design:
  - `design/P2-1-querymodel-aggregate-join-python-design.md`
  - `workitems/P0-81-querymodel-aggregate-sqlite-sql-shape-design.md`
- Review commits:
  - `495526c feat: align aggregate relation sqlite boundary`
  - `5a1ef34 fix: preserve async aggregate validate params`

## Changed Surface

- `src/foggy/dataset_model/aggregate_join.py`
- `src/foggy/dataset_model/semantic/field_validator.py`
- `src/foggy/dataset_model/semantic/service.py`
- `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
- `tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py`
- `tests/test_dataset_model/test_loader_fsscript.py`
- `docs/v3.8-python-alignment/**`

## Quality Checklist

- Scope conformance: reviewed. The runtime/compiler path stays narrow and
  fail-closed for unsupported pivot, timeWindow, groupBy, having, calculated
  fields, post stages, orderBy, multiple carriers, non-LEFT joins, unsupported
  relation filters, unresolved right models, and unsupported aggregations.
- Code hygiene: reviewed. No debug print/logging or temporary branches were
  found in the aggregate relation path. Focused Ruff `F` checks pass.
- Duplication and consolidation: reviewed with risk. Aggregate relation SQL
  lowering is currently concentrated in `SemanticQueryService`, which is
  acceptable for the narrow fixture boundary but should be extracted before
  broader dialect or multi-relation support.
- Complexity and abstraction: reviewed with risk. `_build_aggregate_relation_sqlite_query`
  and `_render_aggregate_outer_filters` are readable enough for the current
  boundary, but they should not become the permanent home for a full optimizer.
- Error handling and edge cases: reviewed. Known unsupported shapes return
  aggregate-specific fail-closed diagnostics; runtime extData filter absence
  fails closed before SQL is returned.
- Contract and compatibility: reviewed. Existing non-aggregate QueryModel
  behavior remains covered by full pytest; aggregate relation carriers remain
  loader-gated.
- Documentation and writeback: reviewed. Workitems and README include focused
  verification evidence; this quality record captures the post-implementation
  review.
- Test alignment: reviewed. Focused aggregate tests, Java snapshot replay,
  neighboring semantic regressions, loader tests, lint, diff check, and full
  pytest were run.

## Findings

- Fixed during review: async validate responses dropped `QueryBuildResult.params`
  for aggregate relation runtime filters, while sync validate preserved them.
  This was corrected in `src/foggy/dataset_model/semantic/service.py` and
  covered by `test_p0_85_async_validate_preserves_runtime_extdata_params`.
- No remaining blocking code-review findings were identified for the declared
  P0-82 through P0-85 boundary.

## Risks / Follow-ups

- SQLite-only boundary: MySQL 5.7, MySQL 8, PostgreSQL, SQL Server, and TMS DB
  aggregate relation lowering are not implemented or fixture-proven yet.
- API metadata boundary: aggregate relation lineage is attached to
  `QueryBuildResult.columns`, but wider API DTO exposure has not been designed
  or reviewed.
- Optimizer boundary: mixed OR predicates, calculated fields over aggregate
  outputs, multi-carrier relations, and broad pushdown planning remain
  fail-closed or out of scope.
- Governance fixture gap: visible-model/system-slice/denied-column aggregate
  combinations need Java-exported fixture expansion before broadening Python
  behavior.

## Recommended Next Skills

- `foggy-test-coverage-audit` before formal acceptance of the aggregate
  relation boundary.
- `foggy-versioned-doc-tracking` for P0-86+ execution check-ins.

## Decision

Decision: `ready-with-risks`.

The P0-82 through P0-85 implementation is complete for the narrow Python-Java
aggregate relation SQLite boundary and has no remaining blocker from this
implementation quality review. The listed risks should drive the next P0
planning items instead of expanding behavior without Java snapshot evidence.
