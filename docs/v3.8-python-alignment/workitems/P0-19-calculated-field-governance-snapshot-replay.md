# P0-19 Calculated Field Governance Snapshot Replay

Date: 2026-06-07

## Goal

Close the P0 governance evidence gap for calculatedFields that depend on denied
physical columns.

This item stays in the engine-neutral snapshot lane. It extends the existing
Java governance exporter and Python replay without changing production engine
logic and without introducing Odoo business-model fixtures.

## Scope

- Java snapshot producer:
  - `JavaGovernanceSnapshotTest.java`
- Python fixture:
  - `tests/fixtures/java_governance_snapshot_parity.json`
- Python replay:
  - `tests/integration/test_java_governance_snapshot_parity.py`
- Manifest:
  - `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- Direct calculatedFields dependency refusal:
  - `query-denied-calculated-direct-dependency-refused`
  - `netAmount = salesAmount - discountAmount`
  - denying `fact_sales.discount_amount` blocks `discountAmount`.
- Transitive calculatedFields dependency refusal:
  - `query-denied-calculated-transitive-dependency-refused`
  - `marginRatio` references `netAmount`, which references `discountAmount`.
  - denying `fact_sales.discount_amount` still blocks the expanded dependency.
- Relation dependency refusal:
  - `query-denied-calculated-relation-dependency-refused`
  - `categoryShare` uses `CALCULATE(... REMOVE(product$categoryName))`.
  - denying `dim_product.category_name` blocks the relation field
    `product$categoryName`.

## Python Gap Decision

Python already validates calculatedFields through `validate_field_access` and
the real `SemanticQueryService` path. P0-19 records Java parity evidence for
the active neutral fixture and replay path instead of changing runtime behavior.

## Acceptance

Required focused checks:

- Java exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py -q`
- Manifest replay:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_governance_snapshot_parity.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_governance_snapshot_parity.py`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Current Verification

Passed:

- Java exporter:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python replay plus manifest:
  `6 passed in 0.45s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest:
  `4049 passed, 232 skipped, 43 warnings in 17.46s`

## Follow-Ups

- Add sanitized error payload snapshots that prove physical-column details do
  not leak.
- Keep aggregate-join governance propagation as P2 with the aggregate-join
  design line.
