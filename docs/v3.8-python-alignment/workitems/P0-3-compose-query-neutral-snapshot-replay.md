# P0-3 Compose Query Neutral Snapshot Replay

Version: v3.8-python-alignment
Priority: P0
Status: snapshot exported; Python replay active
Owner: Python engine
Date: 2026-06-06

## Purpose

Add the Python replay harness for Java compose-query neutral snapshots before
changing compose engine behavior. The harness should stay optional until Java
exports the snapshot file, then become the executable cross-language gate for
derived query, relation reuse, union, join, source alias, qualified refs, and
dialect fallback drift.

Java export is now available from:

- `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/compilation/JavaComposeSnapshotTest.java`

The generated Python fixture is:

- `tests/fixtures/java_compose_snapshot_parity.json`

## Snapshot Contract

Expected fixture path:

- `tests/fixtures/java_compose_snapshot_parity.json`

Required top-level shape:

```json
{
  "schemaVersion": 1,
  "feature": "composeQuery",
  "source": "JavaComposeSnapshotTest",
  "cases": []
}
```

Each case:

```json
{
  "id": "derived-chain-mysql8",
  "dialect": "mysql8",
  "plan": {
    "type": "derived",
    "source": {
      "type": "base",
      "model": "FactSalesModel",
      "columns": ["orderStatus$caption", "salesAmount"]
    },
    "columns": ["orderStatus$caption", "salesAmount"]
  },
  "expected": {
    "sqlMarkers": ["WITH", "order_status"],
    "forbiddenSqlMarkers": ["FROM (WITH"],
    "params": []
  }
}
```

Supported plan node types:

- `base`
- `derived`
- `union`
- `join`

Supported plan node metadata:

- `aliases`: script-local source aliases replayed through
  `QueryPlan.__fsscript_bind_alias__`.

Supported expected assertions:

- `sqlMarkers`
- `forbiddenSqlMarkers`
- `params`
- `errorCode`

## Acceptance Criteria

- Python has a committed replay test target at
  `tests/integration/test_java_compose_snapshot_parity.py`.
- When the Java fixture is present, the test validates snapshot schema and
  compiles each JSON plan through Python `compile_plan_to_sql`.
- P0 manifest marks the compose query lane active and points to the generated
  fixture plus replay test target.

## Test Evidence

- `.venv/bin/python -m ruff check tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py`
  passed.
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed as optional lane: `2 skipped in 0.42s`.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed: `4 passed, 2 skipped in 0.43s`.
- Java producer:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  passed in the Java worktree and wrote the Python fixture.
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed: `2 passed in 0.46s`.
- Manifest + compose replay after lane activation:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_snapshot_parity.py -q --tb=short -rs`
  passed: `6 passed in 0.45s`.
- Full Python baseline after lane activation:
  `.venv/bin/python -m pytest --tb=short -q -rs`
  passed: `4101 passed, 162 skipped, 43 warnings in 17.85s`.

## Exported Snapshot Coverage

Start with engine-neutral ecommerce/demo models, not Odoo:

- base SQL/params on MySQL8,
- derived filter/order/limit SQL and param order,
- union all with aligned projected aliases,
- qualified `left.` / `right.` join references,
- source alias inheritance for post-join derived query projection,
- dropped-column source alias refusal,
- SQL Server fallback shape and forbidden `FROM (WITH` marker.
