---
doc_purpose: Track SQLite live-result parity for the QueryModel aggregate relation happy path.
version: v3.8-python-alignment
priority: P0-83
status: completed
owner: python-engine
---

# P0-83 QueryModel Aggregate SQLite Live Result Parity

Date: 2026-06-12

## Background

P0-82 proves SQL shape. P0-83 executes that shape against SQLite to verify the
central Java behavior: the RHS relation is preaggregated before joining, so
left-side order measures are not multiplied by fact-sales row count.

## Target Outcome

- Execute the aggregate relation happy path through `query_model(...,
  mode="execute")`.
- Seed independent SQLite root/RHS tables in a focused test.
- Verify root columns and aggregate relation outputs match the oracle result.
- Prove fixed RHS filters are applied before aggregation.

## Implementation

- Reused the P0-82 narrow SQLite renderer in the semantic service execution
  path.
- Added a focused SQLite fixture in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.
- The fixture includes multiple completed RHS rows for one order plus a
  cancelled row to prove filter-before-aggregate behavior.

## Acceptance Criteria

- Completed. The live result returns one root order row.
- Completed. The left-side `amount` value remains the root table value and is
  not multiplied by matching RHS rows.
- Completed. The aggregate `salesAmount` is the sum of completed RHS rows only.
- Completed. The `uniqueCustomers` output comes from `count(distinct ...)`.

## Progress Tracking

- Development: completed.
- Testing: completed with focused SQLite execution.
- Experience: N/A; this is backend engine execution with no UI surface.

## Verification

- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  (`14 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`10 passed`)

## Execution Check-in

- Code paths touched:
  - `src/foggy/dataset_model/semantic/service.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
- Self-check:
  - Execution still uses the standard SQLite executor path.
  - No external database lane was opened.
  - The test stays synthetic and engine-neutral.

## Remaining Risks

- Java embedded live-result snapshots are not yet replayed directly by Python;
  this item uses Python SQLite execution plus Java marker fixture evidence.
- External dialect live-result parity is not proven.
- Complex multi-relation and post-aggregate stages remain fail-closed.
