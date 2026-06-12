---
doc_purpose: Track aggregate relation denied-source governance and metadata lineage boundary.
version: v3.8-python-alignment
priority: P0-84
status: completed
owner: python-engine
---

# P0-84 QueryModel Aggregate Governance Metadata Boundary

Date: 2026-06-12

## Background

Java aggregate joins preserve governance across RHS source columns and expose
aggregate output lineage. Python already has general denied-column governance,
but aggregate relation outputs need a separate source-column check because the
selected field is produced by a relation-owned grouped subquery.

## Target Outcome

- Deny aggregate relation output when its RHS physical source column is denied.
- Return a sanitized aggregate-specific error code.
- Attach aggregate relation lineage metadata to `QueryBuildResult.columns`.
- Keep the metadata boundary internal and focused before broad API DTO exposure.

## Implementation

- Added aggregate source-column denied validation in
  `src/foggy/dataset_model/semantic/service.py`.
- Added `QUERYMODEL_AGGREGATE_JOIN_DENIED_SOURCE_COLUMN`.
- Added aggregate relation metadata under each aggregate output column:
  `aggregation`, `sourceCaption`, `sourceMeasure`, `sourceAlias`,
  `sourceExpression`, `aggregateExpression`, and source semantic unit metadata
  when available.
- Added focused governance/metadata tests in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.

## Acceptance Criteria

- Completed. Denying `fact_sales.sales_amount` rejects selecting
  `salesAmount`.
- Completed. The error includes
  `QUERYMODEL_AGGREGATE_JOIN_DENIED_SOURCE_COLUMN`.
- Completed. SQL is not returned for the denied-source case.
- Completed. Successful build results include aggregate relation lineage on
  aggregate output columns.

## Progress Tracking

- Development: completed.
- Testing: completed with focused governance and metadata assertions.
- Experience: N/A; this is backend governance/metadata behavior with no UI
  surface.

## Verification

- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  (`15 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -q`
  (`68 passed`)

## Execution Check-in

- Code paths touched:
  - `src/foggy/dataset_model/semantic/service.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
- Self-check:
  - Governance checks run before SQL generation.
  - The source-column check does not depend on ordinary root-model field
    mapping.
  - Response DTO expansion beyond existing validate/build surfaces remains
    deferred.

## Remaining Risks

- Broader V3 metadata API exposure for aggregate relation lineage remains a
  follow-up.
- Calculated-field execution over aggregate relation outputs remains
  unsupported in the narrow SQLite path.
- Cross-model, multi-relation, and external dialect governance evidence remain
  future work.
