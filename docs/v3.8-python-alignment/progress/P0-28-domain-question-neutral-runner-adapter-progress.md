# P0-28 Domain Question Neutral Runner Adapter Progress

Date: 2026-06-08

## Completed

- Added the neutral runner adapter work item.
- Added the adapter design document.
- Updated the Java snapshot parity manifest entry
  `domain-question-neutral-runner` with the design doc path while keeping
  status `planned` until Java export and Python replay exist.
- Kept Odoo business packs, registry pulls, and generated model changes out of
  this P0 item.

## Verification

Passed:

- Included in the Python manifest focused check:
  `tests/integration/test_java_snapshot_parity_manifest.py`
- Full P0-26/P0-27/P0-28 focused set:
  `12 passed, 8 warnings in 0.55s`

Pending:

- Java neutral domain fixture exporter.
- Python replay adapter implementation.

## Notes

- The next implementation step should start from a Java-exported neutral
  fixture, not from Odoo direct-runner data.
