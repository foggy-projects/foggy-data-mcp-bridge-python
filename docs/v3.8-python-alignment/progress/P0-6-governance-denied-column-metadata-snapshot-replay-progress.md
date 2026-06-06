# P0-6 Governance Denied Column and Metadata Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Extended `JavaGovernanceSnapshotTest` with P0-6 governance contracts:
  - denied physical measure maps to `salesAmount`;
  - denied dimension property maps to `product$categoryName`;
  - unrelated physical column maps to an empty denied-QM set;
  - denied measure in `columns` is refused;
  - denied dimension property in `columns` is refused;
  - unrelated denied physical column passes;
  - denied measure in `orderBy` is refused;
  - metadata denies `salesAmount`;
  - metadata applies `visibleFields - deniedColumns`.
- Regenerated `tests/fixtures/java_governance_snapshot_parity.json`.
- Extended `tests/integration/test_java_governance_snapshot_parity.py` to
  replay the new case types against Python's real `SemanticQueryService` and
  ecommerce demo model.
- Updated `tests/fixtures/java_snapshot_parity_manifest.json` so the active
  governance lane advertises denied-column mapping, query validation, and
  metadata trimming coverage.

## Verification

Java:

```bash
mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest
```

Result: passed. Maven ran the default, MySQL, and Postgres surefire executions
for this test; all passed.

Python focused replay:

```bash
.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q
```

Result: `6 passed in 0.44s`.

Ruff:

```bash
.venv/bin/python -m ruff check tests/integration/test_java_governance_snapshot_parity.py
```

Result: passed.

Full baseline:

```bash
.venv/bin/python -m pytest --tb=short -q -rs
```

Result: `4107 passed, 162 skipped, 43 warnings in 17.48s`.

## Remaining Follow-Ups

- Export and replay visible model allow/deny cases from authority resolution.
- Export and replay cross-model calculated-field governance refusals.
- Export and replay sanitized error payloads that prove no physical column
  leakage.
- Add pivot/domain transport governance propagation snapshots after the
  pivot/domain neutral lane is active.
- Add aggregate join governance propagation only when Python starts the
  aggregate-join P2 implementation.
