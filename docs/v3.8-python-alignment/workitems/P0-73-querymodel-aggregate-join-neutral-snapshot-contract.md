---
doc_role: workitem
doc_purpose: Define the neutral Java snapshot contract required for Python QueryModel aggregate join parity.
version: v3.8-python-alignment
priority: P0
status: implemented
created_at: 2026-06-11
updated_at: 2026-06-11
source_type: parity-fixture-contract
owner_repo: foggy-data-mcp-bridge-python
owner_module: tests/fixtures
---

# P0-73 QueryModel Aggregate Join Neutral Snapshot Contract

## Purpose

Define the Java-owned neutral snapshot envelope that Python needs before
implementing QueryModel aggregate join. This keeps aggregate join on the same
evidence-first path as compose, governance, timeWindow, pivot, domain
transport, semantic scale, and domain question runner parity.

## Delivered

- Added
  `tests/fixtures/java_querymodel_aggregate_join_snapshot_contract.json`.
- Added a planned manifest lane:
  `querymodel-aggregate-join-neutral-snapshots`.
- Added always-on contract tests in
  `tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py`.

## Required Java Export Cases

- Happy SQLite SQL/result case proving RHS preaggregation before LEFT JOIN.
- Left-side measure non-multiplication result evidence.
- Missing RHS groupBy join-key fail-closed error.
- Fixed RHS filter inside the aggregate relation.
- Runtime `extData` RHS filter with bound params.
- Missing runtime `extData` fail-closed error.
- Safe AND join-key/group-key/measure pushdown diagnostics.
- OR and mixed predicate outer-only diagnostics.
- Source physical `deniedColumns` refusal for aggregate outputs and dependent
  calculated fields.
- V3 metadata `aggregateRelation` lineage.

## Acceptance

- The contract fixture is committed and validated by pytest.
- The manifest treats aggregate join as a planned Java-owned lane with explicit
  `javaExportNeeded` and `plannedPythonTests`.
- No Java source or Odoo business model changes are required for this Python
  contract cut.

## Progress

- 2026-06-11: Contract fixture, manifest lane, and pytest contract checks added.

