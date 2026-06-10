# P0-60 Compose MySQL 5.7 Union Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Close the executable compose snapshot inventory gap for MySQL 5.7 `union`
success plans by exporting a Java-authored top-level union snapshot and
replaying it in Python.

## Background

P0-59 closed the MySQL 5.7 `derived` success cell. After that step, the only
remaining non-SQLite compose inventory gaps were MySQL 5.7 `union` and `join`.

The union cell is lower risk than join because it exercises branch projection
alignment and top-level `UNION ALL` SQL shape without adding join relation
scope or qualified left/right reference behavior.

## Scope

- Add one Java compose exporter case for MySQL 5.7 top-level `UNION ALL`.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `25/21` to `26/22`.
- Assert `mysql/union` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- MySQL 5.7 join success cell.
- SQLite compose lane implementation.
- Odoo generated model refresh or registry bundle changes.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `26` total cases and
  `22/22` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `mysql/union` is absent from `missingSuccessCells`.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

Remaining candidates are MySQL 5.7 `join` and the staged SQLite compose lane.
SQLite should still be opened one cell at a time if it is selected before the
MySQL join cell.
