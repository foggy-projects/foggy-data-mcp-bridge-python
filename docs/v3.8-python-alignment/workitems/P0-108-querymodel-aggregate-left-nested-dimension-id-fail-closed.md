---
doc_purpose: Track Python aggregate relation fail-closed evidence for left/root nested dimension $id keys and slices.
version: v3.8-python-alignment
priority: P0-108
status: complete
owner: python-engine
---

# P0-108 QueryModel Aggregate Left Nested Dimension ID Fail-Closed

Date: 2026-06-14

## Scope

P0-108 completes the immediate nested dimension `$id` fail-closed pass by
covering left/root aggregate relation entry points. Python still defers
positive nested `joinTo` path lowering, so nested left-side dimension IDs must
remain fail-closed before SQL generation.

Covered in Python:

- left/root nested dimension `$id` used as an aggregate relation ON key,
- left/root nested dimension `$id` used as a request slice,
- public validate-mode refusal before SQL generation,
- deterministic `AGGREGATE_JOIN_UNSUPPORTED` response,
- no nested dimension field token or physical nested table leakage in refusal
  messages.

Out of scope:

- positive nested dimension SQL lowering,
- nested dimension runtime filters,
- RHS nested dimension `$id` runtime filters,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

Java aggregate relation evidence includes dimension-path joins and O615
dimension `$id` cases. Python P0-101 and P0-107 keep nested `joinTo` paths
fail-closed until a fixture-backed lowering design exists. P0-108 adds the
left/root `$id` ON-key and request-slice variants to that same boundary.

## Implementation

Updated neutral helper:

- `_left_nested_dimension_key_model(...)` now accepts `left_field_override` so
  tests can reuse the existing nested `region -> store` model while selecting a
  specific left aggregate key field.

New tests:

- `test_p0_108_left_nested_dimension_id_on_key_fails_closed` uses `region$id`
  as the aggregate relation ON key and verifies fail-closed behavior.
- `test_p0_108_left_nested_dimension_id_request_slice_fails_closed` keeps the
  aggregate relation ON key on `store$storeId` but applies a `region$id`
  request slice, verifying the same fail-closed behavior.

No engine code was required for this step; the existing nested root dimension
guard already covers `$id` once exercised.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_108 -q`

Result:

`2 passed, 51 deselected in 0.64s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`74 passed in 0.76s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `53 passed in 0.66s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated after P0-108. The latest full baseline from
P0-103 still had only the known MySQL8 real-db timeWindow data/env failure
outside the aggregate relation surface:
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.

## Remaining Boundary

Still open:

- positive nested dimension SQL lowering,
- nested dimension runtime filter fail-closed evidence,
- Java fixture export/replay for accepted nested dimension behavior,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
