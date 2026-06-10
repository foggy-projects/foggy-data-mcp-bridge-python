# P0-63 Compose SQLite Derived Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Close the next staged SQLite compose snapshot inventory gap by exporting a
Java-authored SQLite `derived` success snapshot and replaying it in Python.

## Background

P0-61 opened the SQLite lane with `base-sqlite-cte`. P0-62 completed the
non-SQLite compose success matrix. After P0-62, the remaining compose
inventory gaps were SQLite `derived/union/join`.

This item extends SQLite coverage one cell at a time and keeps the change to
Java/Python snapshot evidence only.

## Scope

- Add one Java compose exporter case for SQLite `DerivedQueryPlan`.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `28/24` to `29/25`.
- Assert `sqlite/derived` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- SQLite union or join success cells.
- Live DB execution or result parity.
- Odoo generated model refresh or registry bundle changes.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `29` total cases and
  `25/25` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `sqlite/derived` is absent from `missingSuccessCells`.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

Continue the SQLite staged lane with SQLite `union`, then SQLite `join` unless
Java drift or fixture shape suggests a different order.
