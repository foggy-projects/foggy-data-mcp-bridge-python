# P0-7 Pivot / Domain Transport Neutral Snapshot Replay

Date: 2026-06-06

## Objective

Activate an offline Java snapshot replay lane for Python Pivot and domain
transport alignment. The first P0-7 slice intentionally avoids Odoo models,
live databases, and broad Pivot pipeline rewrites.

## Scope

- Java snapshot producer:
  - `JavaPivotDomainSnapshotTest.java`
- Python fixture:
  - `tests/fixtures/java_pivot_domain_snapshot_parity.json`
- Python replay:
  - `tests/integration/test_java_pivot_domain_snapshot_parity.py`
- Manifest lane:
  - `pivot-domain-transport-neutral-snapshots`

## Contracts Covered

- Pivot DTO parsing for rows, columns, native metrics, `parentShare`, options,
  output format, and layout.
- Ordinary flat pivot translation into `groupBy`, `columns`,
  `wantGrandTotal`, and `parentShare` sidecar metrics.
- Domain transport renderer shape for SQLite, Postgres, and MySQL8.
- Domain transport params and NULL-safe join predicate markers.
- Empty-column domain transport fail-closed behavior.
- Explicit Java/Python gap evidence for MySQL 5.7: Java renders a derived
  table, while Python currently refuses `mysql5.x`.

## Out Of Scope

- Odoo domain models and registry bundle updates.
- Live DB result parity.
- Pivot tree/cascade expansion.
- Non-additive auxiliary requery output parity.
- `baselineRatio` output parity.
- Production engine code changes.

## Acceptance

- Java producer writes the committed Python fixture and passes focused Maven
  test execution.
- Python replay and manifest tests pass.
- Full Python baseline remains green or any failure is recorded with a concrete
  reason.
