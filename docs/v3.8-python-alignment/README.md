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
- [P0-35-aggregate-alias-field-collision-boundary.md](workitems/P0-35-aggregate-alias-field-collision-boundary.md)
- [P0-36-formula-parity-catalog-and-qm-audit-refresh.md](workitems/P0-36-formula-parity-catalog-and-qm-audit-refresh.md)
- [P0-37-compose-source-alias-qualified-ref-snapshot-expansion.md](workitems/P0-37-compose-source-alias-qualified-ref-snapshot-expansion.md)
- [P0-38-domain-question-warning-report-metadata.md](workitems/P0-38-domain-question-warning-report-metadata.md)
- [P0-39-java-mcp-reactor-verification-baseline.md](workitems/P0-39-java-mcp-reactor-verification-baseline.md)
- [P0-40-compose-script-resolver-resolve-exception-snapshot-replay.md](workitems/P0-40-compose-script-resolver-resolve-exception-snapshot-replay.md)
- [P0-41-domain-question-report-metadata-snapshot-replay.md](workitems/P0-41-domain-question-report-metadata-snapshot-replay.md)
- [P0-42-compose-union-source-alias-shadowing-snapshot-replay.md](workitems/P0-42-compose-union-source-alias-shadowing-snapshot-replay.md)
- [P0-43-compose-stable-relation-reuse-qualified-ref-snapshot-replay.md](workitems/P0-43-compose-stable-relation-reuse-qualified-ref-snapshot-replay.md)
- [P0-44-compose-sqlserver-union-derived-fallback-snapshot-replay.md](workitems/P0-44-compose-sqlserver-union-derived-fallback-snapshot-replay.md)
- [P0-45-compose-sqlserver-cte-capability-parity.md](workitems/P0-45-compose-sqlserver-cte-capability-parity.md)
- [P0-46-compose-sql-shape-manifest.md](workitems/P0-46-compose-sql-shape-manifest.md)
- [P0-47-domain-question-unsupported-construct-snapshot-replay.md](workitems/P0-47-domain-question-unsupported-construct-snapshot-replay.md)
- [P0-48-domain-question-neutral-runner-script-wrapper.md](workitems/P0-48-domain-question-neutral-runner-script-wrapper.md)
- [P0-49-compose-derived-composed-root-wrapper-parity.md](workitems/P0-49-compose-derived-composed-root-wrapper-parity.md)
- [P0-50-compose-success-shape-strict-closure.md](workitems/P0-50-compose-success-shape-strict-closure.md)
- [P0-51-domain-question-toolcallcollector-envelope.md](workitems/P0-51-domain-question-toolcallcollector-envelope.md)
- [P0-52-compose-snapshot-coverage-inventory.md](workitems/P0-52-compose-snapshot-coverage-inventory.md)
- [P0-53-compose-mysql8-join-snapshot-expansion.md](workitems/P0-53-compose-mysql8-join-snapshot-expansion.md)
- [P0-54-registry-odoo-consumer-readonly-audit.md](workitems/P0-54-registry-odoo-consumer-readonly-audit.md)
- [P0-55-compose-postgres-join-snapshot-expansion.md](workitems/P0-55-compose-postgres-join-snapshot-expansion.md)
- [P0-56-compose-postgres-union-snapshot-expansion.md](workitems/P0-56-compose-postgres-union-snapshot-expansion.md)
- [P0-57-compose-sqlserver-union-snapshot-expansion.md](workitems/P0-57-compose-sqlserver-union-snapshot-expansion.md)
- [P0-58-compose-sqlite-lane-evaluation.md](workitems/P0-58-compose-sqlite-lane-evaluation.md)
- [P0-59-compose-mysql57-derived-snapshot-expansion.md](workitems/P0-59-compose-mysql57-derived-snapshot-expansion.md)
- [P0-60-compose-mysql57-union-snapshot-expansion.md](workitems/P0-60-compose-mysql57-union-snapshot-expansion.md)
- [P0-61-compose-sqlite-base-snapshot-expansion.md](workitems/P0-61-compose-sqlite-base-snapshot-expansion.md)
- [P0-62-compose-mysql57-join-snapshot-expansion.md](workitems/P0-62-compose-mysql57-join-snapshot-expansion.md)
- [P0-63-compose-sqlite-derived-snapshot-expansion.md](workitems/P0-63-compose-sqlite-derived-snapshot-expansion.md)
- [P0-64-compose-sqlite-union-snapshot-expansion.md](workitems/P0-64-compose-sqlite-union-snapshot-expansion.md)
- [P0-65-compose-sqlite-join-snapshot-expansion.md](workitems/P0-65-compose-sqlite-join-snapshot-expansion.md)
- [P0-66-timewindow-current-java-snapshot-refresh.md](workitems/P0-66-timewindow-current-java-snapshot-refresh.md)
- [P0-67-timewindow-wow-week-model-alignment.md](workitems/P0-67-timewindow-wow-week-model-alignment.md)
- [P0-68-timewindow-sqlite-live-result-parity.md](workitems/P0-68-timewindow-sqlite-live-result-parity.md)
- [P0-69-pivot-timewindow-refusal-stability.md](workitems/P0-69-pivot-timewindow-refusal-stability.md)
- [P0-70-domain-transport-refusal-replay-hardening.md](workitems/P0-70-domain-transport-refusal-replay-hardening.md)
- [P0-71-domain-transport-sqlite-live-result-replay.md](workitems/P0-71-domain-transport-sqlite-live-result-replay.md)
- [P0-72-querymodel-aggregate-join-python-gap-audit.md](workitems/P0-72-querymodel-aggregate-join-python-gap-audit.md)
- [P0-73-querymodel-aggregate-join-neutral-snapshot-contract.md](workitems/P0-73-querymodel-aggregate-join-neutral-snapshot-contract.md)
- [P0-74-querymodel-aggregate-join-python-replay-skeleton.md](workitems/P0-74-querymodel-aggregate-join-python-replay-skeleton.md)
- [P0-75-querymodel-aggregate-join-java-snapshot-exporter.md](workitems/P0-75-querymodel-aggregate-join-java-snapshot-exporter.md)
- [P0-76-querymodel-aggregate-join-python-snapshot-replay.md](workitems/P0-76-querymodel-aggregate-join-python-snapshot-replay.md)

Current P1/P2 planning records:

- [P1-1-semantic-scale-namespace-opt-out-or-live-result-parity.md](workitems/P1-1-semantic-scale-namespace-opt-out-or-live-result-parity.md)
- [P1-2-querymodel-aggregate-join-parser-fail-closed.md](workitems/P1-2-querymodel-aggregate-join-parser-fail-closed.md)
- [P2-1-querymodel-aggregate-join-python-design.md](workitems/P2-1-querymodel-aggregate-join-python-design.md)

Current active snapshot lanes:

- Formula compiler catalog and QM formula audit
- Time window catalog, including the current Java-produced SQL snapshot with
  9 successful happy cases and no documented Java generation drift, plus
  Python SQLite live-result execution for the same Java happy-case catalog
- Compose query neutral snapshots, including current source-alias and
  qualified-ref fixture coverage plus P0-37 projection/slice/orderBy and
  derived-inheritance expansion, duplicate source-alias fail-closed coverage,
  projected source-alias shadowing refusal, union branch-alias refusal, union
  result-alias qualified refs, stable relation reuse qualified refs, and SQL
  Server embedded composed-source fallback including union-as-derived fallback
  and compose-level SQL Server CTE capability parity, plus exported SQL shape
  manifest replay with strict root-wrapper checks for frozen fallback cases
  and derived-over-composed root-wrapper parity; current successful compose
  snapshots are fully strict on SQL shape, include MySQL8 join success
  evidence, MySQL 5.7 derived/union/join fallback evidence, PostgreSQL
  join/union success evidence, SQL Server top-level union success evidence,
  SQLite base/derived/join CTE evidence, SQLite union evidence, and have an
  executable dialect/plan/status coverage inventory with no missing success
  cells in the current target matrix
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
- Pivot + timeWindow fail-closed boundary evidence, including direct
  validate/execute/governance tests and Java neutral fixture real-service
  replay
- Pivot domain transport large-domain threshold, SQLite bind-limit
  fail-closed snapshots, empty-column refusal, and MySQL5.7 documented gap
  replay, plus Java-fixture-driven SQLite live-result replay for two-field
  NULL-safe and 501-member CTE transport cases
- Domain/question neutral runner normalized tool-argument snapshots, warning
  markers, neutral case-summary report metadata, unsupported construct
  fail-closed metadata, ToolCallCollector-backed record envelopes, and Python
  script wrapper
- Semantic scale neutral snapshots for helper literals, SQL rewriting,
  metadata, and fail-closed carrier-column validation
- Java-style explicit HAVING aggregate alias validation, while keeping Python
  aggregate-slice auto-lift compatibility
- Resolver factory and resolver `resolve(...)` exception structured payload
  replay for MCP compose-script
- Explicit HAVING aggregate alias field-collision fail-closed boundary
- Java MCP focused verification uses the reactor `-am` baseline to avoid stale
  local dependency artifacts
- Registry/Odoo consumer readonly temp-dir audit for current community/pro
  `1.1.10` bundles, without refreshing committed generated Odoo models
- QueryModel aggregate join audit and active snapshot replay lane, with Java 9.2
  capability, Python landing points, required neutral export contract, manifest
  replay skeleton, Java snapshot exporter, committed Java fixture replay, and
  loader fail-closed guard before implementation

Latest P0-78 / P1-2 status:

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
- P0-35 closes the explicit HAVING aggregate-alias shadowing gap left after
  P0-33: selected aggregate aliases now fail closed when explicit HAVING
  references an alias that collides with existing model fields, ignoring case.
  Distinct aliases such as `totalSales` remain valid for HAVING, and compose
  downstream relation naming can still reuse business field names when not
  bypassing same-layer HAVING validation.
- P0-36 refreshes formula parity evidence and QM formula audit. Formula focused
  pytest is green, the demo QM audit exits zero, multiline Odoo formula
  concatenation is parsed correctly, and window formulas are reported as
  skipped instead of FormulaCompiler failures.
- P0-37 expands compose source-alias / qualified-ref fixture coverage with
  PostgreSQL projection, slice, orderBy, and derived-inheritance cases, and
  updates Python replay to use the production `.query(...)` alias propagation
  path for derived snapshot nodes. It also aligns Java/Python fail-closed
  behavior for duplicate source aliases across join sides.
- P0-38 records that neutral domain/question runner `warnings` replay is active
  and that `reports` metadata remains the next fixture-envelope expansion.
- P0-39 closes the recurring Java MCP verification false blocker: module-local
  `-pl foggy-dataset-mcp` can resolve stale local `foggy-dataset-model`
  artifacts, while the reactor `-am` command builds current workspace modules
  and passes the P0-34 exporter and `LocalDatasetAccessorGovernanceTest`.
- P0-40 closes the resolver `resolve(...)` generic exception snapshot gap:
  Java classifies this path as
  `compose-authority-resolve/upstream-failure` with tool phase
  `permission-resolve`, and Python replay now locks the same payload contract.
- P0-41 closes the P0-38 report metadata follow-up: the neutral
  domain/question runner fixture now includes optional
  `neutral-runner-case-summary` reports, and Python replay validates tool,
  model, mode, status, warning count, error count, warning markers, and error
  code against deterministic responses.
- P0-42 closes the P0-37 compose alias follow-up for projected source-alias
  shadowing and union-as-source alias boundaries. Java/Python now reject
  output aliases that shadow visible source aliases, reject branch source
  aliases after a union boundary, accept the union result alias for qualified
  refs, and keep SQL Server embedded composed-source SQL free of `FROM (WITH`.
- P0-43 closes the P0-37 stable relation reuse residual with a test-only
  `reuseKey` neutral snapshot contract and a reused-base derived-join case
  using `left.*` / `right.*` projection, slice, and orderBy refs.
- P0-44 expands SQL Server dialect SQL-shape coverage for
  `derived(union(...))` using the union result alias in projection, slice, and
  orderBy, and aligns root derived-chain output to Java's subquery fallback
  while forbidding embedded `FROM (WITH`.
- P0-45 aligns Python compose-level SQL Server CTE capability with Java:
  `mssql` / `sqlserver` now use subquery fallback in compose lowering while
  lower-level dialect metadata remains unchanged.
- P0-46 adds fixture-level compose SQL shape metadata. Python replay now
  validates stable join/union/where/order/fallback structure for every
  successful compose snapshot and validates root CTE/subquery wrapping for
  explicit strict cases.
- P0-47 expands the neutral domain/question runner fixture with unsupported
  construct cases for pivot+timeWindow, hidden axis functions, and cross-model
  join intent, including error-detail and case-summary report metadata replay.
- P0-48 adds `scripts/run-domain-question-neutral-runner.py` as the local
  entrypoint for the neutral domain/question runner lane. It supports dry-run
  fixture summaries, fixture override through
  `FOGGY_DOMAIN_QUESTION_NEUTRAL_FIXTURE`, and default pytest replay plus
  manifest validation.
- P0-49 closes the P0-46 root-wrapper follow-up for
  `DerivedQueryPlan(source=JoinPlan|UnionPlan)`: Python now returns terminal
  `ComposedSql` for derived-over-composed sources, matching Java, and six
  formerly non-strict compose cases now carry strict SQL-shape checks.
- P0-50 promotes the remaining successful compose snapshot cases to
  `strictSqlShape`, so all `16` current successful compose cases now replay
  full SQL-shape metadata, including root CTE/subquery flags.
- P0-51 adds a deterministic `ToolCallCollector`-backed `collectorRecord`
  envelope to every neutral domain/question runner case. Python replay now
  validates collector session/call count, tool names, normalized arguments,
  sequence/duration, success/error state, and error codes, and the local script
  dry-run reports collector coverage.
- P0-52 adds `scripts/summarize-compose-snapshot-coverage.py` as an executable
  inventory for the Java compose snapshot dialect/plan/status matrix. It keeps
  the `16/16` strict successful SQL-shape replay guarantee active and surfaces
  missing success cells for targeted future exporter expansion.
- P0-53 closes the first P0-52 inventory gap by adding Java-exported
  `join-mysql8-cte` coverage. The compose inventory now reports `17/17`
  strict successful SQL-shape replay and no longer lists `mysql8/join` as a
  missing success cell.
- P0-54 proves registry/Odoo consumer compatibility without generated model
  refresh: community/pro `1.1.10` bundles are pulled into temp directories,
  pass drift checks, and load through the Python model loader with namespace
  `odoo`. The committed demo Odoo directory remains `1.1.9` lock plus drift and
  is intentionally not refreshed in this phase.
- P0-55 adds Java-exported `join-postgres-cte` coverage and removes
  `postgres/join` from the compose inventory missing success cells.
- P0-56 adds Java-exported `union-all-sales-orders-postgres` coverage. The
  accepted Java shape is a direct top-level `SELECT ... UNION ALL ...` output,
  not a forced CTE wrapper.
- P0-57 adds Java-exported `union-all-sales-orders-sqlserver` coverage and
  keeps SQL Server compose fallback guarded against embedded `FROM (WITH`.
- P0-58 evaluates SQLite as a separate compose dialect lane. After P0-55
  through P0-57, the compose inventory reports `24` total cases and `20/20`
  strict successful SQL-shape replay. Remaining missing success cells are
  MySQL non-CTE `derived/union/join` and SQLite `base/derived/union/join`.
- P0-59 adds Java-exported MySQL 5.7 derived filter/order/limit fallback
  coverage. The compose inventory now reports `25` total cases and `21/21`
  strict successful SQL-shape replay. Remaining missing success cells are
  MySQL non-CTE `union/join` and SQLite `base/derived/union/join`.
- P0-60 adds Java-exported MySQL 5.7 top-level union coverage. The compose
  inventory reports `26` total cases and `22/22` strict successful SQL-shape
  replay before the SQLite base expansion.
- P0-61 opens the staged SQLite compose lane with Java-exported
  `base-sqlite-cte` coverage. The compose inventory now reports `27` total
  cases and `23/23` strict successful SQL-shape replay. Remaining missing
  success cells are MySQL non-CTE `join` and SQLite `derived/union/join`.
- P0-62 adds Java-exported MySQL 5.7 join fallback coverage. The compose
  inventory now reports `28` total cases and `24/24` strict successful
  SQL-shape replay. The non-SQLite compose success matrix is now complete;
  remaining missing success cells are SQLite `derived/union/join`.
- P0-63 adds Java-exported SQLite derived filter/order/limit CTE coverage. The
  compose inventory now reports `29` total cases and `25/25` strict successful
  SQL-shape replay. Remaining missing success cells are SQLite `union/join`.
- P0-64 adds Java-exported SQLite top-level union coverage. The compose
  inventory now reports `30` total cases and `26/26` strict successful
  SQL-shape replay. Remaining missing success cell is SQLite `join`.
- P0-65 adds Java-exported SQLite join CTE coverage. The compose inventory now
  reports `31` total cases and `27/27` strict successful SQL-shape replay.
  `missingSuccessCells` is empty for the current target matrix.
- P0-66 refreshes the current Java timeWindow SQL snapshot. The committed
  snapshot now has 8 Java-success SQL cases and one explicit
  `wow-week-happy` generation error for the current Java
  `salesDate$week` catalog/model drift; Python replays every Java-success
  case through validate mode.
- P0-67 closes that `wow-week-happy` drift by exposing logical
  `salesDate$week` in the Java ecommerce demo/query model, refreshing the Java
  snapshot to 9 SQL success cases with no generation errors, and updating
  Python replay to require all 9 success cases.
- P0-68 adds Python SQLite live-result execution for all 9 current Java
  timeWindow happy cases, with deterministic execution-only range overrides
  and result checks for comparative arithmetic, cumulative first rows, rolling
  materialization, and post-calculated aliases.
- P0-69 hardens the Java-aligned `pivot + timeWindow` unsupported boundary:
  Python now checks request-builder preservation, validate/execute fail-closed
  order before timeWindow field validation, governance build failure, and
  real-service replay of the Java neutral runner unsupported case.
- P0-70 hardens the domain transport boundary replay lane with explicit
  fixture-presence and parameterized replay for SQLite 501 transport, SQLite
  1000-bind fail-closed, empty-column refusal, and the MySQL 5.7 Java-only
  derived-table gap.
- P0-71 adds Java-fixture-driven SQLite live-result replay for domain
  transport: the two-field NULL-safe case and the 501-member CTE transport
  case now execute assembled Python SQL against SQLite and match independent
  oracle SQL.
- P0-72 audits Java 9.2 QueryModel aggregate join against Python
  QueryModel/ordinary join/governance/metadata landing points. It freezes the
  conclusion that Python needs a separate aggregate relation carrier and
  neutral Java snapshot contract before implementation, instead of extending
  ordinary explicit joins or touching Odoo models first.
- P0-73 adds the aggregate-join neutral snapshot contract fixture and planned
  manifest lane, covering SQL/result, fail-closed, metadata lineage,
  diagnostics, and governance cases required from Java.
- P0-74 adds the Python contract replay skeleton and makes
  `queryModelAggregateJoin` part of the always-on manifest feature matrix while
  keeping production aggregate-join SQL unimplemented.
- P0-75 adds the Java QueryModel aggregate join neutral snapshot exporter. It
  writes `target/parity/_querymodel_aggregate_join_snapshot.json` with the 10
  contract cases from P0-73, giving Python a concrete replay source while
  production SQL lowering remains unimplemented.
- P0-76 promotes the Java aggregate-join snapshot into a committed Python
  fixture and activates offline replay for SQL markers, Java result evidence,
  fail-closed errors, diagnostics, and metadata lineage. Python runtime
  aggregate join remains fail-closed until a dedicated carrier and SQL lowering
  land.
- P1-2 adds the first bounded engine guard: Python now recognizes explicit
  aggregate join declarations and Java-style `leftJoinAggregate(...)` DSL
  sentinels, then fails closed with `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED`
  instead of loading them as ordinary joins.
- P0-77 adds the minimal Python aggregate relation carrier: proxy DSL calls now
  preserve RHS filters, group keys, measures, aliases, and join conditions in a
  structural carrier while keeping runtime aggregate join fail-closed.
- P0-78 adds loader-side carrier extraction for explicit aggregate relation
  dicts and Java-style `leftJoinAggregate(...)` DSL objects. The loader now
  reports `carrier_count=N` before rejecting unsupported aggregate joins.
- P1-1 records the remaining semantic-scale choice: namespace opt-out parity or
  live DB/result parity.
- P2-1 records the initial Python aggregate-join design boundary before any
  implementation work.
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
- Python P0-41 focused replay and manifest passed:
  `6 passed in 0.17s`.
- Python P0-42 focused join/union coverage passed:
  `3 passed in 0.10s`.
- Python P0-42 focused compose replay and manifest passed:
  `6 passed in 0.52s`.
- Python P0-43 local regression passed:
  `1 passed in 0.13s`.
- Python P0-43 focused compose replay and manifest passed:
  `6 passed in 0.50s`.
- Python P0-44 focused SQL Server union-derived fallback coverage passed:
  `8 passed in 0.15s`.
- Python P0-44 compose compilation suite passed:
  `275 passed in 0.70s`.
- Python P0-45 focused fallback and replay coverage passed:
  `36 passed in 0.17s`.
- Python P0-45 compose compilation suite passed:
  `275 passed in 0.68s`.
- Python P0-46 focused compose replay and manifest passed:
  `6 passed in 0.49s`.
- Python P0-47 focused replay and manifest passed:
  `6 passed in 0.17s`.
- Python P0-48 script dry-run plus focused replay and manifest passed:
  `7 passed in 0.33s`.
- Python P0-49 focused compose replay passed:
  `2 passed in 0.50s`.
- Python P0-49 compose compilation regression passed:
  `85 passed in 0.33s`; focused `ruff --select F` passed.
- Python P0-50 focused replay and manifest passed:
  `6 passed in 0.49s`; strict coverage check reported
  `success 16 strict 16 non_strict 0`.
- Python P0-51 dry-run plus focused replay and manifest passed:
  `collectorRecordCount 6 / caseCount 6`; `7 passed in 0.27s`; focused ruff
  passed.
- Python P0-51 script default run passed:
  `6 passed in 0.15s`.
- Python P0-53 focused compose replay, coverage inventory, and manifest passed:
  `7 passed in 0.66s`; coverage inventory reported `17/17` strict successful
  SQL-shape replay.
- Python P0-53 focused ruff passed:
  `.venv/bin/ruff check scripts/summarize-compose-snapshot-coverage.py tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`.
- Python P0-54 focused registry/Odoo readonly audit passed:
  `.venv/bin/python -m pytest tests/integration/test_odoo_registry_consumer_readonly.py -q`
  with `2 passed in 1.18s`.
- Python P0-54 focused ruff passed:
  `.venv/bin/ruff check tests/integration/test_odoo_registry_consumer_readonly.py`.
- Java P0-59 focused exporter passed:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`.
- Python P0-59 coverage inventory reported:
  `25` cases and `21/21` strict successful SQL-shape replay.
- Java P0-60 focused exporter passed:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`.
- Python P0-60 coverage inventory reported:
  `26` cases and `22/22` strict successful SQL-shape replay.
- Python P0-48 script default run passed:
  `6 passed in 0.15s`.
- Full Python pytest after P0-48 passed:
  `4083 passed, 232 skipped, 53 warnings in 17.66s`.
- Java P0-42 focused exporter passed:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest,JoinCompileTest`
  with `22` tests passed.
- Java P0-43 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  across the default, MySQL, and PostgreSQL executions.
- Java P0-44 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  across the default, MySQL, and PostgreSQL executions.
- Java P0-45 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  across the default, MySQL, and PostgreSQL executions.
- Java P0-47 MCP reactor exporter passed:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`.
- Java P0-46 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  across the default, MySQL, and PostgreSQL executions.
- Java P0-49 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  across the default, MySQL, and PostgreSQL executions.
- Java P0-50 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  across the default, MySQL, and PostgreSQL executions.
- Java P0-51 MCP reactor exporter passed:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`.
- Java P0-53 focused exporter passed with SQLite-only profile:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  with `1` test passed.
- Python full coverage after P0-43 passed:
  `4080 passed, 232 skipped, 53 warnings in 17.97s`.
- Python full coverage after P0-44 passed:
  `4082 passed, 232 skipped, 53 warnings in 22.16s`.
- Python full coverage after P0-45 passed:
  `4082 passed, 232 skipped, 53 warnings in 17.98s`.
- Python full coverage after P0-42 passed:
  `4079 passed, 232 skipped, 53 warnings in 18.72s`.
- Python P0-32 focused replay passed:
  `14 passed in 0.45s`.
- Python P0-33 focused coverage passed:
  `174 passed in 7.41s`.
- Python P0-34 focused coverage passed:
  `8 passed, 9 warnings in 0.51s`.
- Python P0-40 focused replay and manifest passed:
  `6 passed, 8 warnings in 0.51s`.
- Python P0-35 focused and full coverage passed:
  `175 passed in 7.61s`; `4073 passed, 232 skipped, 52 warnings in 17.68s`.
- Python P0-36 focused coverage passed:
  `2 passed in 0.43s`; `192 passed in 0.83s`; QM formula audit exit 0.
- Python P0-37 focused replay passed:
  `6 passed in 0.48s`; join-focused regression `3 passed in 0.13s`; replay
  harness ruff check passed.
- Python full coverage after P0-36/P0-37/P0-38/P1-1/P2-1 records passed:
  `4075 passed, 232 skipped, 52 warnings in 17.46s`.
- Java P0-37 focused exporter passed:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest` and
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest,JoinCompileTest`.
- Java P0-39 MCP reactor focused coverage passed:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaComposeScriptToolErrorSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
  and
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=LocalDatasetAccessorGovernanceTest -Dsurefire.failIfNoSpecifiedTests=false test`.
- Java P0-40 MCP reactor exporter passed:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaComposeScriptToolErrorSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`.
- Java P0-41 MCP reactor exporter passed:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaDomainQuestionNeutralRunnerSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`.
- Java P0-32 focused exporter passed with SQLite-only profile:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaSemanticScaleSnapshotTest`.
- Full Python pytest and Java focused Maven status are recorded in the
  P0-26/P0-27 progress docs; P0-29/P0-30/P0-31 focused evidence is recorded in
  their progress docs. P0-32/P0-33/P0-34/P0-35/P0-36/P0-39/P0-40/P0-41/P0-42
  /P0-43/P0-44/P0-45/P0-46/P0-47/P0-48/P0-49/P0-50/P0-51/P0-53/P0-54
  evidence is recorded in their progress docs.
