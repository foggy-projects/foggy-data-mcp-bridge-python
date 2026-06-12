---
doc_purpose: Plan the runtime/compiler refusal boundary for aggregate relation carriers before SQL lowering.
version: v3.8-python-alignment
priority: P0-79
status: planned
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

- Focused test proves a model with `aggregate_relations` refuses before SQL
  generation.
- Focused test proves a normal QueryModel without aggregate relations still
  compiles/runs through the existing baseline path.
- Existing P0-76/P0-78 aggregate snapshot and loader tests remain green.
- No SQL lowering or live-result behavior is introduced in this item.

## Non-Goals

- Do not implement RHS preaggregation SQL.
- Do not attach aggregate relation carriers to production-loaded QueryModels.
- Do not touch Odoo generated models or registry bundle versions.
- Do not expand product/UI behavior.

## Verification Plan

- `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -q`
- New focused runtime/compiler refusal pytest.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
- `git diff --check`

## Next

After P0-79, the safe order is P0-80 loader attachment behind the same refusal
boundary, then P0-81 minimal SQLite SQL-shape design. Production aggregate join
execution must wait for SQL/result/governance/diagnostics parity evidence.
