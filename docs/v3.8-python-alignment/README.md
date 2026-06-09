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
- [P0-30-semantic-scale-factor-money-units.md](workitems/P0-30-semantic-scale-factor-money-units.md)
- [P0-31-domain-question-neutral-runner-snapshot-replay.md](workitems/P0-31-domain-question-neutral-runner-snapshot-replay.md)
- [P0-32-semantic-scale-neutral-snapshot-replay.md](workitems/P0-32-semantic-scale-neutral-snapshot-replay.md)
- [P0-33-having-aggregate-alias-strictness.md](workitems/P0-33-having-aggregate-alias-strictness.md)
- [P0-34-compose-script-resolver-factory-exception-snapshot-replay.md](workitems/P0-34-compose-script-resolver-factory-exception-snapshot-replay.md)

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
- Domain/question neutral runner normalized tool-argument snapshots
- Semantic scale neutral snapshots for helper literals, SQL rewriting,
  metadata, and fail-closed carrier-column validation
- Java-style explicit HAVING aggregate alias validation, while keeping Python
  aggregate-slice auto-lift compatibility
- Resolver factory exception structured payload replay for MCP compose-script

Latest P0-34 status:

- P0-26 extends the active MCP compose-script error snapshot lane with
  `missing-user-id-header` and `missing-namespace-header`.
- Python aligns header bridge `ValueError` / `TypeError` failures to Java's
  `internal-error` payload.
- P0-27 extends the runtime snapshot lane with `pure_runtime` capability
  policy allow/deny cases and adds Python preflight for registered-but-denied
  runtime capability calls.
- P0-28 records the neutral domain/question runner adapter design without
  touching Odoo business models.
- P0-29 adds Java-aligned runtime `dictionaryDiscovery` metadata in Python,
  including fail-closed sensitive/hidden/error handling and context-scoped
  discovery cache isolation.
- P0-30 adds Java-aligned `semanticScaleFactor` support in Python for fact
  properties, dimension properties, measures, formula-backed fields, query SQL,
  and V3 metadata.
- P0-31 activates the neutral domain/question runner lane with a Java exporter
  and Python replay for normalized `dataset.query_model` tool arguments. The
  first fixture covers grouped query, calculated/time-window query, and
  denied-field fail-closed behavior without LLM, Odoo, registry pull, or
  generated model refresh.
- P0-32 promotes semantic scale into the active Java snapshot parity catalog,
  with Java-exported helper, SQL, metadata, and fail-closed cases replayed by
  Python against a neutral synthetic model.
- P0-33 closes the direct ordinary aggregate-measure `request.having` drift:
  explicit HAVING now requires a selected aggregate alias such as
  `sum(salesAmount) as totalSales`, while aggregate-measure `slice` shorthand
  continues to auto-lift to HAVING for compatibility.
- P0-34 closes the generic resolver factory exception drift in
  `dataset.compose_script`: Java's `resolver-factory-exception` snapshot is
  replayed by Python as `internal-error/internal`, while resolver factory
  `None` remains `host-misconfig/internal`.
- The Java exporters write:
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`.
  and `tests/fixtures/java_compose_script_snapshot_parity.json`.
  and `tests/fixtures/java_domain_question_neutral_runner_parity.json`.
  and `tests/fixtures/java_semantic_scale_snapshot_parity.json`.
- Python P0-26/P0-27 focused replay and manifest passed:
  `12 passed, 8 warnings in 0.59s`.
- Python P0-29 focused coverage passed:
  `7 passed in 0.48s`.
- Python P0-30 focused coverage passed:
  `8 passed in 0.48s`.
- Python P0-31 focused replay passed:
  `2 passed in 0.15s`.
- Python P0-32 focused replay passed:
  `14 passed in 0.45s`.
- Python P0-33 focused coverage passed:
  `174 passed in 7.41s`.
- Python P0-34 focused coverage passed:
  `8 passed, 9 warnings in 0.51s`.
- Java P0-32 focused exporter passed with SQLite-only profile:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaSemanticScaleSnapshotTest`.
- Full Python pytest and Java focused Maven status are recorded in the
  P0-26/P0-27 progress docs; P0-29/P0-30/P0-31 focused evidence is recorded in
  their progress docs. P0-32/P0-33/P0-34 evidence is recorded in their
  progress docs.
