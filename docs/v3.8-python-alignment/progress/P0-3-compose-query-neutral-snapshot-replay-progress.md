# P0-3 Compose Query Neutral Snapshot Replay Progress

Version: v3.8-python-alignment
Status: snapshot exported; Python replay active
Date: 2026-06-06

## Completed

- Added `tests/integration/test_java_compose_snapshot_parity.py`.
- Defined the optional fixture path
  `tests/fixtures/java_compose_snapshot_parity.json`.
- Defined supported JSON plan node types: `base`, `derived`, `union`, `join`.
- Defined expected assertion keys: `sqlMarkers`, `forbiddenSqlMarkers`,
  `params`, and `errorCode`.
- Extended replay support for plan node `aliases`, mapped to
  `QueryPlan.__fsscript_bind_alias__`.
- Extended expected-error handling to cover both snapshot plan construction and
  SQL compilation.
- Added Java snapshot producer in the Java worktree:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/compilation/JavaComposeSnapshotTest.java`.
- Generated `tests/fixtures/java_compose_snapshot_parity.json`.
- Updated `tests/fixtures/java_snapshot_parity_manifest.json` so
  `compose-query-neutral-snapshots` is now `active`.

## Touched Paths

- `tests/integration/test_java_compose_snapshot_parity.py`
- `tests/fixtures/java_compose_snapshot_parity.json`
- `tests/fixtures/java_snapshot_parity_manifest.json`
- `docs/v3.8-python-alignment/workitems/P0-3-compose-query-neutral-snapshot-replay.md`
- `docs/v3.8-python-alignment/progress/P0-3-compose-query-neutral-snapshot-replay-progress.md`

Java worktree touched path:

- `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/compilation/JavaComposeSnapshotTest.java`

## Test Evidence

- `.venv/bin/python -m ruff check tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py`
  passed.
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed as optional lane: `2 skipped in 0.42s`.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed: `4 passed, 2 skipped in 0.43s`.
- `.venv/bin/python -m pytest --tb=short -q -rs`
  passed: `4099 passed, 164 skipped, 43 warnings in 17.90s`.
- Java producer:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed in the Java worktree.
- Python replay after fixture export:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed: `2 passed in 0.46s`.
- Ruff after fixture export:
  `.venv/bin/python -m ruff check tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py`
  passed.
- Manifest + compose replay after lane activation:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed: `6 passed in 0.45s`.
- Full Python baseline after lane activation:
  `.venv/bin/python -m pytest --tb=short -q -rs`
  passed: `4101 passed, 162 skipped, 43 warnings in 17.85s`.

## Self Check

- [x] Focused replay test skipped cleanly while Java fixture was absent.
- [x] Java producer generated the compose snapshot fixture.
- [x] Python replay executes real snapshot cases.
- [x] Ruff passed after activating the fixture.
- [x] P0 manifest passes after activating the compose lane.
- [x] Full pytest baseline passed after activating the fixture.
- [x] No production engine files changed.
- [x] No registry/generated Odoo files touched.

## Next Step

Run the post-export verification set: ruff, manifest replay, focused compose
replay, and full Python pytest baseline.
