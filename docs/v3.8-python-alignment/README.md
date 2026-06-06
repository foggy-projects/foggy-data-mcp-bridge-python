# Python Engine v3.8 Alignment Line

This directory tracks the Python engine alignment upgrade against current Java
3.x / 9.x engine capabilities.

Naming basis:

- The active Python branch is `v3.0/engine-skill-next`.
- The alignment target includes Java `docs/v3.0` and Java 9.x engine work.
- Python had versioned docs through `docs/v1.16`; this independent
  `docs/v3.8-python-alignment` root keeps the alignment iteration isolated from
  any future Python v3.0 mainline docs.

Planning starts with:

- [P0-python-alignment-upgrade-plan.md](P0-python-alignment-upgrade-plan.md)

Current P0 execution records:

- [BUG-P0-1-formula-parity-catalog-path-drift.md](workitems/BUG-P0-1-formula-parity-catalog-path-drift.md)
- [BUG-P0-1-postgres-realdb-profile-gate.md](workitems/BUG-P0-1-postgres-realdb-profile-gate.md)
- [P0-2-java-snapshot-parity-manifest.md](workitems/P0-2-java-snapshot-parity-manifest.md)
- [P0-3-compose-query-neutral-snapshot-replay.md](workitems/P0-3-compose-query-neutral-snapshot-replay.md)
- [P0-4-compose-script-tool-neutral-snapshot-replay.md](workitems/P0-4-compose-script-tool-neutral-snapshot-replay.md)
- [P0-5-governance-neutral-snapshot-replay.md](workitems/P0-5-governance-neutral-snapshot-replay.md)
- [P0-6-governance-denied-column-metadata-snapshot-replay.md](workitems/P0-6-governance-denied-column-metadata-snapshot-replay.md)
- [P0-7-pivot-domain-transport-neutral-snapshot-replay.md](workitems/P0-7-pivot-domain-transport-neutral-snapshot-replay.md)
- [P0-8-pivot-output-sqlite-snapshot-replay.md](workitems/P0-8-pivot-output-sqlite-snapshot-replay.md)
- [BUG-P0-9-pivot-output-cache-key-collision.md](workitems/BUG-P0-9-pivot-output-cache-key-collision.md)
- [P0-10-pivot-grand-total-output-snapshot-replay.md](workitems/P0-10-pivot-grand-total-output-snapshot-replay.md)
- [P0-11-pivot-row-subtotal-output-snapshot-replay.md](workitems/P0-11-pivot-row-subtotal-output-snapshot-replay.md)
- [P0-12-pivot-parent-share-output-snapshot-replay.md](workitems/P0-12-pivot-parent-share-output-snapshot-replay.md)
- [P0-13-pivot-baseline-ratio-output-snapshot-replay.md](workitems/P0-13-pivot-baseline-ratio-output-snapshot-replay.md)
- [P0-14-pivot-non-additive-output-snapshot-replay.md](workitems/P0-14-pivot-non-additive-output-snapshot-replay.md)
- [P0-15-pivot-domain-large-domain-snapshot-replay.md](workitems/P0-15-pivot-domain-large-domain-snapshot-replay.md)
- [P0-16-pivot-domain-governance-snapshot-replay.md](workitems/P0-16-pivot-domain-governance-snapshot-replay.md)

Current active snapshot lanes:

- Formula compiler catalog
- Time window catalog
- Compose query neutral snapshots
- Compose script tool/runtime neutral snapshots
- Governance / permission visible-model neutral snapshots, including
  queryModel, Pivot, and domain transport denied-column propagation
- Pivot / domain transport neutral snapshots
- Pivot real flat/grid SQLite output snapshots, including grandTotal,
  rowSubtotals, parentShare, baselineRatio output, and ordinary flat
  non-additive subtotal/grandTotal output
- Pivot domain transport large-domain threshold and SQLite bind-limit
  fail-closed snapshots

Latest P0-16 status:

- Python focused replay passed:
  `2 passed in 0.64s`.
- Java exporter passed with SQLite-focused execution:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Manifest replay passed:
  `6 passed in 0.66s`.
- Full Python pytest currently shows compose runtime pause/resume baseline
  instability:
  - First run: `2 failed, 4039 passed, 232 skipped, 45 warnings in 17.58s`.
  - Second run: `1 failed, 4040 passed, 232 skipped, 43 warnings in 17.82s`.
  - The three observed failing tests each passed when rerun directly.
- `java_governance_snapshot_parity.json` now contains 16 cases, including
  Pivot denied-row-axis, Pivot parentShare native-metric denial, and domain
  transport denied-column fail-closed propagation.
- Remaining governance gaps after P0-16: authority-resolved visible model
  allow/deny cases, cross-model calculated-field refusals, sanitized error
  payload snapshots, and aggregate-join governance propagation.
