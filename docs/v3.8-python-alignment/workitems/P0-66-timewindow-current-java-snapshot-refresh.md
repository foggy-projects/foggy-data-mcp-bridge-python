# P0-66 TimeWindow Current Java Snapshot Refresh

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Purpose

Refresh the Java-produced timeWindow SQL snapshot from the current Java
engine and make Python replay the full current success set instead of only the
two post-scalar calculated-field cases.

## Background

The Python alignment gap matrix still listed timeWindow as mostly aligned but
needing a current Java snapshot refresh for relative-date and dialect behavior.
The existing Java `TimeWindowParitySnapshotTest` only exported
`yoy-month-post-calc-growth-happy` and
`rolling_7d-post-calc-gap-happy`.

When expanded to the whole catalog, current Java 9.1 still cannot generate SQL
for the legacy `wow-week-happy` catalog case because the current
`FactSalesQueryModel` lacks `salesDate$week`. This item records that as an
explicit generation drift instead of treating it as Python parity success.

## Scope

- Expand the Java timeWindow snapshot producer to cover all happy catalog
  cases that the current Java model can generate.
- Record the current Java `wow-week-happy` generation error in the committed
  snapshot.
- Refresh Python `tests/integration/_time_window_parity_snapshot.json`.
- Upgrade Python golden diff coverage to require the current Java success set
  plus the documented generation drift.
- Keep Python catalog replay and SQLite execution tests active.

## Out of Scope

- Changing production timeWindow SQL generation in Java or Python.
- Fixing the Java `salesDate$week` model/catalog drift.
- Odoo generated model refresh or registry bundle changes.
- Full token-by-token normalized SQL comparison for multi-CTE timeWindow SQL.

## Acceptance Criteria

- Java `TimeWindowParitySnapshotTest` passes and writes the refreshed snapshot.
- Python committed snapshot contains 8 Java SQL snapshots and one documented
  `wow-week-happy` generation error.
- Python replay validates the current Java success set and cross-checks each
  Java-success case through `SemanticQueryService` validate mode.
- Existing Python Java catalog replay and SQLite timeWindow execution tests
  remain green.
- Version docs and manifest identify the new evidence and the remaining
  Java catalog/model drift.

## Expected Follow-Up

Next timeWindow work should either fix/export the Java `wow-week-happy`
catalog/model mismatch or move to live DB/result parity for the current 8-case
success set. Pivot+timeWindow refusal should stay in the separate
pivot/domain edge-behavior lane.
