---
doc_role: workitem
doc_purpose: Add the first Python parser/loader fail-closed guard for unsupported QueryModel aggregate join declarations.
version: v3.8-python-alignment
priority: P1
status: implemented
created_at: 2026-06-11
updated_at: 2026-06-11
source_type: bounded-engine-guard
owner_repo: foggy-data-mcp-bridge-python
owner_module: dataset_model.loader
---

# P1-2 QueryModel Aggregate Join Parser Fail-Closed

## Purpose

Prevent unsupported QueryModel aggregate join declarations from silently loading
as ordinary explicit joins while Python aggregate join SQL lowering is still
unimplemented.

## Delivered

- Added `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED` loader guard.
- Added Java-style `leftJoinAggregate(...)` / aggregate relation sentinel
  support in `TableModelProxy` so the loader can recognize and reject that DSL
  path explicitly.
- Added loader tests for:
  - explicit `aggregateJoins` contract refusal;
  - Java-style `fo.leftJoinAggregate(fs)...on(...)` refusal.

## Non-Scope

- No RHS derived aggregate relation SQL rendering.
- No aggregate output source lineage or V3 metadata implementation.
- No pushdown diagnostics implementation in Python runtime.
- No Odoo aggregate join model work.

## Acceptance

- Aggregate join declarations do not become ordinary `explicit_joins`.
- The failure marker is stable enough for future Java fixture replay:
  `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED`.
- Existing ordinary multi-fact join loader behavior remains covered by the
  existing tests.

## Progress

- 2026-06-11: Parser/evaluator sentinel and loader fail-closed tests added.

