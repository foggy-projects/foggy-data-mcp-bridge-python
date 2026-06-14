---
doc_purpose: Track Python aggregate relation fail-closed evidence for left/root nested dimension runtime request slices.
version: v3.8-python-alignment
priority: P0-110
status: complete
owner: python-engine
---

# P0-110 QueryModel Aggregate Left Nested Dimension Runtime Slice Fail-Closed

Date: 2026-06-14

## Scope

P0-110 closes the immediate left/root runtime slice gap left after P0-108 and
P0-109. Python still defers positive nested `joinTo` path lowering, so a
left/root request slice on a nested dimension path must fail closed before SQL
generation even when the filter value is supplied from request context.

Covered in Python:

- left/root nested dimension `$id` request slices,
- runtime value supplied through `context.attributes.extData`,
- public validate-mode refusal before SQL generation,
- deterministic `AGGREGATE_JOIN_UNSUPPORTED` response,
- no nested dimension field token, runtime key, or physical nested table leakage
  in refusal messages.

Out of scope:

- positive nested dimension SQL lowering,
- RHS nested dimension runtime filters, already covered by P0-109,
- aggregate relation ON-key runtime expressions,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

Java aggregate relation acceptance includes nested dimension path behavior as a
positive engine capability. Python has not opened that lowering path yet. Until
fixture-backed lowering is implemented, P0-110 keeps the Python boundary
fail-closed for context-backed left/root request slices.

## Implementation

New test:

- `test_p0_110_left_nested_dimension_id_runtime_slice_fails_closed` builds a
  model whose aggregate relation uses a non-nested left ON key, then requests a
  slice on left/root nested dimension `region$id` with
  `value = {"extData": "regionKey"}`.
- The request supplies `context.attributes.extData.regionKey = 1`.
- Validate mode returns `AGGREGATE_JOIN_UNSUPPORTED` with the existing nested
  root dimension marker and does not leak `region$id`, `regionKey`, or
  `dim_region`.

No engine code was required for this step; the existing nested root dimension
guard takes precedence before SQL generation.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_110 -q`

Result:

`1 passed, 54 deselected in 0.65s`

Aggregate SQLite alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`

Result:

`55 passed in 0.66s`

Aggregate parity combo command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`76 passed in 0.75s`

Static checks:

- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated in this step. Latest full-suite baseline
remains P0-103: `1 failed, 4242 passed, 168 skipped`, with the known unrelated
MySQL8 real-DB timeWindow matrix failure.

## Remaining Boundary

Still open:

- positive nested dimension SQL lowering,
- aggregate relation ON-key runtime expression evidence if that syntax is later
  admitted,
- Java fixture export/replay for accepted nested dimension behavior,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
