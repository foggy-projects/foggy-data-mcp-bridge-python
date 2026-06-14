---
doc_purpose: Track the Python-side O615 aggregate relation v4 contract skeleton.
version: v3.8-python-alignment
priority: P0-112
status: complete
owner: python-engine
---

# P0-112 QueryModel Aggregate O615 Contract Skeleton

Date: 2026-06-14

## Scope

P0-112 turns the P0-111 O615 fixture export plan into an executable Python-side
contract skeleton. It keeps the current Java v3 aggregate snapshot replay
unchanged and adds a separate v4 contract-only fixture for the O615 explicit
join graph cases.

Covered in Python:

- `querymodel-aggregate-join-4` contract-only fixture,
- six required Java O615 probe cases,
- required evidence keys for future replay,
- manifest tracking for the planned v4 contract,
- a test that verifies v4 is not marked Java-exported yet.

Out of scope:

- Java exporter implementation,
- committed v4 parity snapshot,
- positive Python O615 explicit join graph lowering,
- Odoo/TMS generated business model changes,
- external dialect implementation.

## Implementation

New fixture:

- `tests/fixtures/java_querymodel_aggregate_join_o615_snapshot_contract.json`

New contract test:

- `tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py`

Manifest update:

- `tests/fixtures/java_snapshot_parity_manifest.json` now lists the O615 v4
  contract fixture and contract test as active Python evidence.
- The manifest keeps `querymodel-aggregate-join-4` under `plannedExtensions`
  and the new test asserts it is not present in `javaExported`.

## Required O615 Cases

The contract skeleton pins these Java tests:

- `aggregateRelationO615ProbeNoColumnsWithAccessShouldResolveJoinPath`,
- `aggregateRelationO615ProbeExpressJoinNoColumnsShouldResolveJoinPath`,
- `aggregateRelationO615TenantGuardShouldBypassFieldAccessWithoutLeaking`,
- `aggregateRelationO615ProbeExpressJoinDimensionIdSliceShouldResolveJoinPath`,
- `aggregateRelationO615ProbeRhsDimensionFilterShouldResolveJoinPath`,
- `aggregateRelationO615ProbeRhsJoinDimensionFilterShouldResolveJoinPath`.

## Verification

Focused contract command:

`.venv/bin/python -m pytest tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py -q`

Result:

`3 passed in 0.04s`

Manifest command:

`.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py -q`

Result:

`4 passed in 0.03s`

JSON validation:

`.venv/bin/python -m json.tool tests/fixtures/java_querymodel_aggregate_join_o615_snapshot_contract.json >/dev/null && .venv/bin/python -m json.tool tests/fixtures/java_snapshot_parity_manifest.json >/dev/null`

Result:

- passed

Aggregate contract/replay combo:

`.venv/bin/python -m pytest tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`13 passed in 0.08s`

Aggregate parity combo:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py -q`

Result:

`79 passed in 0.76s`

Static checks:

- `.venv/bin/python -m ruff check tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated in this step. Latest full-suite baseline
remains P0-103: `1 failed, 4242 passed, 168 skipped`, with the known unrelated
MySQL8 real-DB timeWindow matrix failure.

## Remaining Boundary

Still open:

- Java exporter update to emit `querymodel-aggregate-join-4`,
- committed v4 parity fixture,
- Python v4 replay test for actual exported cases,
- positive O615 explicit join graph lowering after replay is active,
- external dialect and production TMS evidence.
