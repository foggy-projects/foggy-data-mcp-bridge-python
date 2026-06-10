# P0-59 Compose MySQL 5.7 Derived Snapshot Expansion

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Close the executable compose snapshot inventory gap for MySQL 5.7 `derived`
success plans by exporting a Java-authored non-CTE fallback snapshot and
replaying it in Python.

## Background

P0-52 made compose dialect/plan coverage visible. P0-53 and P0-55 through
P0-57 closed MySQL8 join, PostgreSQL join/union, and SQL Server union success
cells. P0-58 kept SQLite as a separate staged lane. The remaining non-SQLite
coverage gaps after P0-58 were MySQL 5.7 `derived`, `union`, and `join`.

The lowest-risk next cell is MySQL 5.7 `derived` because it exercises the
existing subquery fallback path with filter, order, and limit markers without
introducing branch merge or join relation-scope behavior.

## Scope

- Add one Java compose exporter case for MySQL 5.7 derived filter/order/limit.
- Refresh the committed Python Java compose snapshot fixture.
- Raise Python compose snapshot coverage thresholds from `24/20` to `25/21`.
- Assert `mysql/derived` is no longer a missing success cell.
- Record the exported shape in the Java snapshot parity manifest.

## Out of Scope

- MySQL 5.7 union or join success cells.
- SQLite compose lane implementation.
- Odoo generated model refresh or registry bundle changes.
- Production compiler rewrites beyond replaying the Java-exported snapshot.

## Acceptance Criteria

- Java `JavaComposeSnapshotTest` passes and exports the new snapshot.
- Python compose snapshot coverage inventory reports `25` total cases and
  `21/21` strict successful cases.
- Python replay validates the refreshed Java compose fixture.
- `mysql/derived` is absent from `missingSuccessCells`.
- Version docs and manifest identify the new evidence.

## Expected Follow-Up

P0-60 should target MySQL 5.7 `union` if the current Java/Python fallback shape
can be exported as a strict low-risk success cell. MySQL 5.7 `join` should
follow after union unless the inventory or Java drift suggests a different
order.
