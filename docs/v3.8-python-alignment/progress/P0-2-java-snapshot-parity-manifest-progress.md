# P0-2 Java Snapshot Parity Manifest Progress

Version: v3.8-python-alignment
Status: ready for acceptance
Date: 2026-06-06

## Completed

- Added `tests/fixtures/java_snapshot_parity_manifest.json`.
- Added `tests/integration/test_java_snapshot_parity_manifest.py`.
- Registered active formula and timeWindow evidence.
- Registered planned export requirements for compose query, script runtime tool,
  pivot/domain transport, governance, and neutral domain fixture runner.

## Touched Paths

- `tests/fixtures/java_snapshot_parity_manifest.json`
- `tests/integration/test_java_snapshot_parity_manifest.py`
- `docs/v3.8-python-alignment/workitems/P0-2-java-snapshot-parity-manifest.md`
- `docs/v3.8-python-alignment/progress/P0-2-java-snapshot-parity-manifest-progress.md`

## Test Evidence

- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py -q --tb=short`
  passed: `4 passed in 0.03s`.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_formula_parity.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/integration/test_time_window_golden_diff.py -q --tb=short -rs`
  passed: `74 passed in 0.54s`.

## Self Check

- [x] Focused manifest pytest passed.
- [x] Relevant existing parity tests still pass.
- [x] Full pytest baseline checked in P0-1; deferred in this P0-2 slice because
  this change only adds a manifest and integration test gate.
- [x] No production engine files changed.
- [x] No Java/registry/generated Odoo files touched.

## Next Step

Use the manifest's planned lanes as the export checklist for P0-3 Java neutral
snapshot generation, starting with compose query SQL/runtime snapshots.
