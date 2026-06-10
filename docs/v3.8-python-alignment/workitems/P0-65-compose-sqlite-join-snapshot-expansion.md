# P0-65 Compose SQLite Join Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Close the final compose snapshot dialect/plan success inventory gap by
exporting a Java-authored SQLite `JoinPlan` success snapshot and replaying it
in Python.

## Background

P0-61, P0-63, and P0-64 closed SQLite `base`, `derived`, and `union`.
After P0-64, SQLite `join` was the only remaining `missingSuccessCells`
entry in the compose coverage inventory.

This item keeps the scope limited to Java/Python snapshot evidence and does
not change production compiler behavior.

## Scope

- Add one Java compose exporter case for SQLite inner `JoinPlan`.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `30/26` to `31/27`.
- Assert `sqlite/join` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- Live DB execution or result parity.
- Odoo generated model refresh or registry bundle changes.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `31` total cases and
  `27/27` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `missingSuccessCells` is empty for the target compose dialect/plan matrix.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

With the current compose dialect/plan success inventory closed, the next P0
planning step should decide whether to broaden live DB/result parity, refresh
timeWindow evidence, or open a new bounded snapshot lane.
