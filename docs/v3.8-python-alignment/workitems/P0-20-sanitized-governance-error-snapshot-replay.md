# P0-20 Sanitized Governance Error Snapshot Replay

Date: 2026-06-07

## Goal

Close the P0 governance evidence gap for denied-column error sanitization.

The snapshot contract allows high-level QM field markers in governance refusal
errors, but forbids leaking physical table or column identifiers from
`deniedColumns`.

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

- Measure denial error sanitization:
  - `query-denied-sanitized-measure-error-payload`
  - error must mention `salesAmount`
  - error must not mention `fact_sales` or `sales_amount`
- Relation-field denial error sanitization:
  - `query-denied-sanitized-relation-error-payload`
  - error must mention `product$categoryName`
  - error must not mention `dim_product` or `category_name`

## Python Gap Decision

Python already returns sanitized governance validation errors from the real
`SemanticQueryService` path. P0-20 records Java parity evidence and keeps the
behavior under the active fixture replay.

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
  - first run hit a transient Maven incremental testCompile/classpath failure on
    existing pivot/preagg classes
  - immediate rerun passed:
    `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python replay plus manifest:
  `6 passed in 0.47s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest:
  `4049 passed, 232 skipped, 43 warnings in 22.00s`

## Follow-Ups

- Keep aggregate-join governance propagation as P2 with the aggregate-join
  design line.
