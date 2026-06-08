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
- [BUG-P0-17-compose-runtime-pause-suspension-publication.md](workitems/BUG-P0-17-compose-runtime-pause-suspension-publication.md)
- [P0-18-authority-visible-model-governance-snapshot-replay.md](workitems/P0-18-authority-visible-model-governance-snapshot-replay.md)
- [P0-19-calculated-field-governance-snapshot-replay.md](workitems/P0-19-calculated-field-governance-snapshot-replay.md)
- [P0-20-sanitized-governance-error-snapshot-replay.md](workitems/P0-20-sanitized-governance-error-snapshot-replay.md)
- [P0-21-compose-script-rows-result-shape-snapshot-replay.md](workitems/P0-21-compose-script-rows-result-shape-snapshot-replay.md)
- [P0-22-compose-script-host-misconfig-snapshot-replay.md](workitems/P0-22-compose-script-host-misconfig-snapshot-replay.md)
- [P0-23-compose-script-remote-principal-mismatch-snapshot-replay.md](workitems/P0-23-compose-script-remote-principal-mismatch-snapshot-replay.md)
- [P0-24-compose-script-remote-missing-binding-snapshot-replay.md](workitems/P0-24-compose-script-remote-missing-binding-snapshot-replay.md)
- [P0-25-compose-script-input-context-error-snapshot-replay.md](workitems/P0-25-compose-script-input-context-error-snapshot-replay.md)
- [P0-26-compose-script-header-bridge-error-snapshot-replay.md](workitems/P0-26-compose-script-header-bridge-error-snapshot-replay.md)
- [P0-27-compose-script-capability-policy-snapshot-replay.md](workitems/P0-27-compose-script-capability-policy-snapshot-replay.md)
- [P0-28-domain-question-neutral-runner-adapter.md](workitems/P0-28-domain-question-neutral-runner-adapter.md)
- [P0-29-runtime-dictionary-discovery-metadata.md](workitems/P0-29-runtime-dictionary-discovery-metadata.md)

Current active snapshot lanes:

- Formula compiler catalog
- Time window catalog
- Compose query neutral snapshots
- Compose script tool/runtime neutral snapshots, including execute-mode rows
  envelope shape and MCP host-misconfig structured error payloads
- Governance / permission visible-model neutral snapshots, including
  authority-resolved visible model allow/deny, queryModel, Pivot, and domain
  transport denied-column propagation, plus calculatedFields direct,
  transitive, and relation dependency refusals, and sanitized governance error
  payload checks
- Pivot / domain transport neutral snapshots
- Pivot real flat/grid SQLite output snapshots, including grandTotal,
  rowSubtotals, parentShare, baselineRatio output, and ordinary flat
  non-additive subtotal/grandTotal output
- Pivot domain transport large-domain threshold and SQLite bind-limit
  fail-closed snapshots

Latest P0-29 status:

- P0-26 extends the active MCP compose-script error snapshot lane with
  `missing-user-id-header` and `missing-namespace-header`.
- Python now aligns header bridge `ValueError` / `TypeError` failures to
  Java's `internal-error` payload while keeping resolver factory failures as
  `host-misconfig`.
- P0-27 extends the runtime snapshot lane with `pure_runtime` capability
  policy allow/deny cases and adds Python preflight for registered-but-denied
  runtime capability calls.
- P0-28 records the neutral domain/question runner adapter design without
  touching Odoo business models.
- P0-29 adds Java-aligned runtime `dictionaryDiscovery` metadata in Python,
  including fail-closed sensitive/hidden/error handling and context-scoped
  discovery cache isolation.
- The Java exporters write:
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`.
  and `tests/fixtures/java_compose_script_snapshot_parity.json`.
- Python P0-26/P0-27 focused replay and manifest passed:
  `12 passed, 8 warnings in 0.59s`.
- Python P0-29 focused coverage passed:
  `7 passed in 0.48s`.
- Full Python pytest and Java focused Maven status are recorded in the
  P0-26/P0-27 progress docs; P0-29 focused evidence is recorded in its
  progress doc.
