# P0-32 Semantic Scale Neutral Snapshot Replay Progress

Date: 2026-06-08

## Completed

- Added Java `JavaSemanticScaleSnapshotTest` exporter for semantic scale
  helper, SQL, metadata, and fail-closed cases.
- Generated `tests/fixtures/java_semantic_scale_snapshot_parity.json`.
- Added Python replay against a neutral synthetic model.
- Added `semanticScaleFactor` as an active Java snapshot parity manifest
  feature.
- Recorded the Java/Python calculated-field parameterization difference in the
  fixture through separate `javaParams` and `pythonParams` expectations.

## Verification

Passed:

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaSemanticScaleSnapshotTest`
  - `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- `.venv/bin/python -m pytest tests/integration/test_java_semantic_scale_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py tests/test_dataset_model/test_semantic_scale_factor.py -q`
  - `14 passed in 0.45s`

Not used as final evidence:

- `mvn test -pl foggy-dataset-model -Dtest=JavaSemanticScaleSnapshotTest`
  invokes the default `multi-db` profile and requires local Docker databases.
  It reached `test-postgres` and failed because `localhost:15432` was not
  running.

## Notes

- Java rejects direct `HAVING` over a non-aggregate semantic-scale measure and
  requires the aggregate alias path, for example
  `sum(salesAmountYuan) as totalSalesAmountYuan` with
  `having totalSalesAmountYuan > 1000`.
- Python P0-30 still keeps its existing aggregate-measure HAVING behavior. A
  stricter Java-aligned validation pass can be handled as a separate follow-up
  if we decide to close that behavioral gap.
- Namespace-level semantic scale opt-out remains outside this snapshot replay
  scope.
