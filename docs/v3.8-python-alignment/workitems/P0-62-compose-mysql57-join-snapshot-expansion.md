# P0-62 Compose MySQL 5.7 Join Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Close the final non-SQLite compose snapshot inventory gap by exporting a
Java-authored MySQL 5.7 `join` success snapshot and replaying it in Python.

## Background

P0-59 and P0-60 closed MySQL 5.7 `derived` and `union`. P0-61 opened the
SQLite staged lane with a base snapshot. After P0-61, the only remaining
non-SQLite compose gap was MySQL 5.7 `join`.

This item verifies the non-CTE join fallback shape without touching Odoo
business models or changing production compiler behavior.

## Scope

- Add one Java compose exporter case for MySQL 5.7 `JoinPlan`.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `27/23` to `28/24`.
- Assert `mysql/join` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- SQLite derived, union, or join success cells.
- Live DB execution or result parity.
- Odoo generated model refresh or registry bundle changes.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `28` total cases and
  `24/24` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `mysql/join` is absent from `missingSuccessCells`.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

The non-SQLite compose success matrix is complete after this item. Continue
with SQLite staged cells, starting with SQLite `derived`, then `union`, then
`join` unless Java drift suggests a different order.
