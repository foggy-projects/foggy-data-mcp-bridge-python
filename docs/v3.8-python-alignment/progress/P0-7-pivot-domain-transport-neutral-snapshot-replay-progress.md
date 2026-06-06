# P0-7 Pivot / Domain Transport Neutral Snapshot Replay Progress

Date: 2026-06-06

## Progress

- Added Java exporter for offline Pivot/domain transport contracts.
- Added Python replay for Pivot DTO parsing, ordinary flat pivot translation,
  renderer fragments, renderer params, and NULL-safe predicate markers.
- Activated the `pivot-domain-transport-neutral-snapshots` manifest lane.
- Recorded MySQL 5.7 domain transport as an explicit parity gap:
  Java has `DERIVED_TABLE` support; Python currently fails closed for
  `mysql5.x`.

## Verification

- Java producer passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaPivotDomainSnapshotTest`.
- Focused Python replay plus manifest passed:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  -> `6 passed in 0.41s`.
- Ruff passed:
  `.venv/bin/python -m ruff check tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`.
- First full pytest run exposed an intermittent compose pause/resume failure:
  `tests/compose/runtime/test_handler_pause.py::TestFailClosed::test_resume_after_reject`
  failed with `run_ctx.suspension is None` plus a suspend timeout thread
  warning. The failing test passed when run directly.
- Second full pytest run passed:
  `.venv/bin/python -m pytest --tb=short -q -rs`
  -> `4109 passed, 162 skipped, 43 warnings in 17.59s`.

## Follow-Up

- Real flat/grid output snapshots are covered by P0-8.
- Add subtotal and grand-total output snapshots.
- Add non-additive auxiliary requery shape snapshots.
- Add `baselineRatio` output snapshots.
- Add large-domain threshold and limit refusal snapshots.
- Add pivot/domain governance propagation snapshots.
