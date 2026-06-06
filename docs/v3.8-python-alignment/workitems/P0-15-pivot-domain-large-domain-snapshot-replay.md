# P0-15 Pivot Domain Large-Domain Snapshot Replay

Date: 2026-06-06

## Goal

Extend the active P0-7 Pivot/domain transport snapshot lane with large-domain
threshold and fail-closed limit evidence.

This item is intentionally a snapshot/replay alignment task. It does not change
Python production renderer limits and does not touch Odoo business models.

## Scope

- Java snapshot producer:
  - `JavaPivotDomainSnapshotTest.java`
- Python fixture:
  - `tests/fixtures/java_pivot_domain_snapshot_parity.json`
- Python replay:
  - `tests/integration/test_java_pivot_domain_snapshot_parity.py`

## Contracts Covered

- SQLite large-domain transport path for a single-field domain with 501 tuples.
- `largeDomainThreshold=500` marker in the Java-exported fixture.
- Java/Python shared CTE placement and parameter-count evidence for the 501
  tuple path.
- Explicit documented Java/Python limit gap:
  - Java SQLite renderer accepts 1000 bind parameters under its larger guard.
  - Python SQLite renderer intentionally fails closed above 999 bind
    parameters with `PIVOT_DOMAIN_TRANSPORT_REFUSED`.

## Python Gap Decision

Python keeps the stricter SQLite bind limit for now. P0-15 records the behavior
as a documented parity gap instead of increasing production limits without live
database evidence.

## Acceptance

Required focused checks:

- Java exporter:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaPivotDomainSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py -q`
- Manifest replay:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py -q`
- Scoped lint:
  `.venv/bin/python -m ruff check tests/integration/test_java_pivot_domain_snapshot_parity.py`

## Current Verification

Passed:

- Java exporter:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python focused replay:
  `2 passed in 0.39s`
- Manifest replay:
  `6 passed in 0.41s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest baseline:
  `4041 passed, 232 skipped, 43 warnings in 17.66s`

## Follow-Ups

- Add pivot/domain governance propagation snapshots.
- Keep MySQL 5.7 live large-domain evidence as a P2/support-scope decision.
- Do not expand tree/cascade or Odoo domain packs as part of this low-risk P0
  lane.
