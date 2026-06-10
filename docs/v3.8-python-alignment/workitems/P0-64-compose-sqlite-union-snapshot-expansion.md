# P0-64 Compose SQLite Union Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Close the SQLite `union` compose snapshot inventory gap by exporting a
Java-authored SQLite `UnionPlan` success snapshot and replaying it in Python.

## Background

P0-61 and P0-63 closed SQLite `base` and `derived`. After P0-63, the remaining
SQLite staged compose gaps were `union/join`.

This item continues the same low-risk snapshot evidence lane without changing
production compiler behavior or touching Odoo business models.

## Scope

- Add one Java compose exporter case for SQLite top-level `UnionPlan`.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `29/25` to `30/26`.
- Assert `sqlite/union` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- SQLite join success cell.
- Live DB execution or result parity.
- Odoo generated model refresh or registry bundle changes.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `30` total cases and
  `26/26` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `sqlite/union` is absent from `missingSuccessCells`.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

Continue the SQLite staged lane with SQLite `join`, which should close the
remaining compose dialect/plan success inventory gap.
