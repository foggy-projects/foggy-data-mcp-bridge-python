---
doc_purpose: Record Python replay activation for the Java v3 aggregate relation snapshot.
version: v3.8-python-alignment
priority: P0-93
status: complete
owner: python-engine
---

# P0-93 QueryModel Aggregate v3 Python Replay

Date: 2026-06-13

## Scope

P0-93 imports the Java v3 aggregate relation snapshot into the Python replay
lane and updates the contract gates. Runtime behavior changes are handled by
P0-94 and P0-95.

## Implementation

- Replaced `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`
  with the Java v3 export.
- Updated the snapshot contract fixture to require
  `querymodel-aggregate-join-3` and 29 case ids.
- Extended replay assertions for diagnostics cases, `orderBy`, `returnTotal`,
  `totalSql`, `totalData`, and sanitized forbidden error markers.
- Updated `tests/fixtures/java_snapshot_parity_manifest.json` so the aggregate
  relation lane advertises the v3 29-case snapshot.

## Verification

- Python replay command:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
- Result: `10 passed in 0.08s` during activation; `10 passed in 0.05s` after
  P0-95.

## Remaining Boundary

P0-93 is replay-only. Cases that require Python runtime behavior are still
bounded to the later low-risk runtime slices and do not imply broad Odoo or
external dialect support.
