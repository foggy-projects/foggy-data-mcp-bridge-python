# P0-61 Compose SQLite Base Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Open the SQLite compose dialect lane with the smallest stable compiler
contract: one Java-authored `base` success snapshot replayed by Python.

## Background

P0-58 evaluated SQLite as a separate staged compose lane. P0-59 and P0-60 then
closed MySQL 5.7 derived and union cells, leaving MySQL 5.7 `join` and SQLite
`base/derived/union/join` as the visible compose inventory gaps.

SQLite should start with `base` before derived, union, or join because it proves
the dialect is accepted by Java's compose compiler and gives Python one strict
SQL-shape contract without relation-scope complexity.

## Scope

- Add one Java compose exporter case for SQLite `BaseModelPlan`.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `26/22` to `27/23`.
- Assert `sqlite/base` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- SQLite derived, union, or join success cells.
- Live SQLite execution or result parity.
- MySQL 5.7 join.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `27` total cases and
  `23/23` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `sqlite/base` is absent from `missingSuccessCells`.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

Next candidates are SQLite `derived` or MySQL 5.7 `join`. SQLite `union` and
`join` should wait until SQLite derived/base behavior is stable in the
inventory.
