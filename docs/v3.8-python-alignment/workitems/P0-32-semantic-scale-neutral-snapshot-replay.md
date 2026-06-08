# P0-32 Semantic Scale Neutral Snapshot Replay

Date: 2026-06-08

## Goal

Promote P0-30 `semanticScaleFactor` from Python-only focused coverage into the
shared Java snapshot parity catalog.

## Scope

- Java snapshot exporter:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/parity/JavaSemanticScaleSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_semantic_scale_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_semantic_scale_snapshot_parity.py`
- Manifest gate:
  `tests/fixtures/java_snapshot_parity_manifest.json`
  `tests/integration/test_java_snapshot_parity_manifest.py`

## Contract

- Java exports helper literal formatting for semantic scale SQL.
- Java exports representative SQL markers for dimension properties, aggregate
  alias `HAVING`, calculated fields, and formula-backed fields.
- Java exports semantic unit metadata markers.
- Java exports invalid carrier-column fail-closed behavior.
- Python replays the Java fixture through a neutral synthetic model and checks
  Python-side SQL markers, parameters, metadata, and fail-closed validation.

## Explicit Non-Scope

- Full token-by-token SQL equivalence across Java and Python.
- Live DB result parity for every dialect.
- Namespace-level semantic scale opt-out config parity.
- Domain-specific accounting or currency semantics.

## Acceptance

- Java exporter passes with SQLite-only focused Maven command.
- Python replay and manifest tests pass.
- The active manifest contains `semanticScaleFactor` coverage.
- P0-30's optional neutral snapshot follow-up is closed.
