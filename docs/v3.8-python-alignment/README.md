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

Current active snapshot lanes:

- Formula compiler catalog
- Time window catalog
- Compose query neutral snapshots
- Compose script tool/runtime neutral snapshots
- Governance / permission visible-model neutral snapshots
- Pivot / domain transport neutral snapshots
- Pivot real flat/grid SQLite output snapshots, including grandTotal,
  rowSubtotals, parentShare, baselineRatio output, and ordinary flat
  non-additive subtotal/grandTotal output
- Pivot domain transport large-domain threshold and SQLite bind-limit
  fail-closed snapshots

Latest P0-15 status:

- Python focused replay passed:
  `2 passed in 0.39s`.
- Java exporter passed with SQLite-focused execution:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`.
- Full Python pytest passed:
  `4041 passed, 232 skipped, 43 warnings in 17.66s`.
- `java_pivot_domain_snapshot_parity.json` now contains nine cases, including
  `domain-sqlite-large-501-transport` and
  `domain-sqlite-python-bind-limit-gap`.
- Remaining Pivot/domain gaps after P0-15: grid/cascade/tree non-additive
  evidence, pivot/domain governance propagation, SQL Server cascade oracle,
  and MySQL 5.7 live support-scope evidence.
