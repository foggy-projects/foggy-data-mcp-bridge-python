---
doc_role: workitem
doc_purpose: Add Python replay scaffolding for future Java QueryModel aggregate join snapshots without enabling production aggregate join SQL.
version: v3.8-python-alignment
priority: P0
status: implemented
created_at: 2026-06-11
updated_at: 2026-06-11
source_type: parity-replay-skeleton
owner_repo: foggy-data-mcp-bridge-python
owner_module: tests/integration
---

# P0-74 QueryModel Aggregate Join Python Replay Skeleton

## Purpose

Make aggregate join visible in the Python snapshot parity harness before Java
exports the real fixture. This prevents the gap from staying only in docs while
avoiding premature production implementation.

## Delivered

- `test_java_snapshot_parity_manifest.py` now requires the
  `queryModelAggregateJoin` feature to exist in the manifest.
- `test_java_querymodel_aggregate_join_snapshot_contract.py` validates the
  contract-only fixture, planned Java exporter name, planned Python replay
  target, diagnostics contract, and metadata lineage keys.
- The planned parity replay target is reserved as
  `tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py`.

## Runtime Boundary

The skeleton is intentionally contract-only. It does not compile aggregate
join SQL and does not claim runtime parity. Production behavior remains
fail-closed until Java neutral fixtures are available and Python implements a
dedicated aggregate relation carrier.

## Acceptance

- The manifest gate fails if aggregate join disappears from the parity matrix.
- The contract test fails if required cases, diagnostics, or metadata lineage
  keys are removed.
- Current active parity tests remain green.

## Progress

- 2026-06-11: Planned manifest lane and always-on contract replay added.

