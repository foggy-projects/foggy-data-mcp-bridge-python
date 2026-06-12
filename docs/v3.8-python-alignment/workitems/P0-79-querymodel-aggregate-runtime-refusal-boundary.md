---
doc_purpose: Plan the runtime/compiler refusal boundary for aggregate relation carriers before SQL lowering.
version: v3.8-python-alignment
priority: P0-79
status: completed
owner: python-engine
---

# P0-79 QueryModel Aggregate Runtime Refusal Boundary

Date: 2026-06-12

## Background

P0-77 introduced the aggregate relation carrier and P0-78 added loader-side
carrier extraction while preserving fail-closed loading. Before any future work
attaches aggregate relations to loaded QueryModels, the compiler/runtime layer
needs an explicit refusal boundary so aggregate relation carriers cannot be
silently ignored or executed through ordinary QueryModel paths.

## Target Outcome

- Any `DbTableModelImpl` carrying non-empty `aggregate_relations` must fail
  closed before SQL generation or execution if aggregate-join lowering is not
  enabled.
- The refusal must use the existing aggregate join code:
  `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED`.
- The error must be sanitized and must not expose physical SQL fragments or
  hidden source columns.
- Ordinary QueryModel, explicit join, compose, pivot, timeWindow, and domain
  transport paths must remain unchanged.

## Proposed Touchpoints

- `src/foggy/dataset_model/semantic/service.py`
  - add or reuse a pre-SQL validation boundary for models with
    `aggregate_relations`.
- `src/foggy/dataset_model/impl/model/__init__.py`
  - no model-shape expansion expected unless tests expose a missing field.
- `tests/test_dataset_model/`
  - focused runtime/compiler refusal tests with synthetic carrier models.
- `tests/integration/`
  - keep Java aggregate join snapshot replay unchanged and always-on.

## Acceptance Criteria

- Completed. Focused test proves a model with `aggregate_relations` refuses
  before SQL generation through synchronous validate, asynchronous validate,
  `build_query_with_governance`, and direct `_build_query` compiler paths.
- Completed. Focused test proves a normal QueryModel without aggregate
  relations still compiles through the existing validate baseline path.
- Completed. Existing P0-76/P0-78 aggregate snapshot and loader tests remain
  green.
- Completed. No SQL lowering or live-result behavior is introduced in this
  item.

## Implementation

- Added shared `AGGREGATE_JOIN_UNSUPPORTED_CODE` in
  `src/foggy/dataset_model/aggregate_join.py`.
- Reused that code from the loader fail-closed path and from semantic query
  service runtime/compiler checks.
- Added an aggregate relation refusal boundary in:
  - `SemanticQueryService.query_model`
  - `SemanticQueryService.query_model_async`
  - `SemanticQueryService.build_query_with_governance`
  - `SemanticQueryService._build_query`
- The refusal response includes only sanitized model-level metadata:
  error code, requested model name, and carrier count. It does not include
  generated SQL, table SQL, or physical column fragments.
- Added focused tests in
  `tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py`.

## Non-Goals

- Do not implement RHS preaggregation SQL.
- Do not attach aggregate relation carriers to production-loaded QueryModels.
- Do not touch Odoo generated models or registry bundle versions.
- Do not expand product/UI behavior.

## Verification Plan

- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  (`5 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -q`
  (`66 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`10 passed`)
- Pending final workspace check: `git diff --check`

## Execution Check-in

- Code paths touched:
  - `src/foggy/dataset_model/aggregate_join.py`
  - `src/foggy/dataset_model/impl/loader/__init__.py`
  - `src/foggy/dataset_model/semantic/service.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py`
- Self-check:
  - Aggregate relation carriers fail closed before SQL generation.
  - Ordinary QueryModel compilation remains unchanged.
  - Error detail is sanitized and intentionally does not expose physical SQL.
  - Loader fail-closed behavior still uses the same refusal code.

## Next

After P0-79, the safe order is P0-80 loader attachment behind the same refusal
boundary, then P0-81 minimal SQLite SQL-shape design. Production aggregate join
execution must wait for SQL/result/governance/metadata/diagnostics parity
evidence.
