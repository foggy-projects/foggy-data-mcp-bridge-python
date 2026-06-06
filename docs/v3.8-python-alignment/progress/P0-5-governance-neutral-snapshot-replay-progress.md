# P0-5 Governance Neutral Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Added Java snapshot producer for governance parity.
- Generated `tests/fixtures/java_governance_snapshot_parity.json`.
- Added Python replay test for:
  - snapshot schema
  - `ModelBinding.fieldAccess` null vs empty-list semantics
  - `fieldAccess`, `deniedColumns`, and `systemSlice` forwarding
  - missing visible-model binding fail-closed compile error
- Activated the manifest lane `permission-visible-model-snapshots`.

## Verification

Java:

```bash
mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest
```

Result: passed. Maven ran the default, MySQL, and Postgres surefire executions
for this test; all passed.

Python:

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

- Export and replay queryModel denied-column SQL refusal cases.
- Export and replay metadata/visible-model trimming cases.
- Export and replay cross-model calculated-field governance refusals.
- Export and replay sanitized error payloads that prove no physical column
  leakage.
- Keep Odoo business models out of this lane until neutral governance snapshots
  are stable.
