# P0 Java/Python Engine Parity Audit

## 文档作用

- doc_type: parity-audit
- status: draft-audit
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 盘点 Python engine 与 Java engine 的当前对齐程度，明确剩余缺口、证据缺口和下一步执行顺序。

## Scope

审计范围：

- `query_model` base query lifecycle。
- `CALCULATE / REMOVE` 与 calculatedFields/formula compiler。
- `timeWindow`。
- `pivot`。
- `compose_script / CTE / stable relation`。
- governance: `systemSlice`、`deniedColumns`、fieldAccess、masking。
- dialect evidence: SQLite、MySQL8、PostgreSQL、SQL Server、MySQL 5.7。

不在本轮直接编码，不修改 public DSL，不扩大 Pivot 已签收边界。

## Evidence Read

| Area | Evidence |
|---|---|
| Python Pivot v1.10 | `docs/v1.10/acceptance/version-signoff.md` |
| Python v1.10 README | `docs/v1.10/README.md` |
| Python migration baseline | `docs/migration-progress.md` |
| Python timeWindow quality | `docs/v1.5/quality/P1-timeWindow-Python-parity-implementation-quality.md` |
| Python timeWindow calculatedFields quality | `docs/v1.5/quality/P1-timeWindow-calculatedFields-implementation-quality.md` |
| Python stable relation quality | `docs/v1.5/quality/S7-stage7-implementation-quality.md` |
| Java Pivot 9.1 signoff | `docs/9.1.0/acceptance/version-signoff.md` in Java workspace |
| Java Pivot 9.2 roadmap | `docs/9.2.0/README.md` in Java workspace |
| MCP prompt contract | `src/foggy/mcp/schemas/descriptions/query_model_v3.md` |

## Summary

| Domain | Python Status | Java Alignment Judgment | Next Action |
|---|---|---|---|
| Base query_model lifecycle | mostly aligned | aligned-with-refresh-needed | Refresh evidence against current code and permissions. |
| Join / field resolution / formulas | mostly aligned | aligned-with-refresh-needed | Re-run formula parity and governance tests. |
| CALCULATE / REMOVE | partial-current | needs-audit | Highest-priority audit because prompt exposes it and recent dirty work touched this path. |
| timeWindow | implemented with historical evidence | aligned-with-evidence-refresh-needed | Promote v1.5 evidence into current v1.11 signoff matrix; verify no regression. |
| timeWindow + calculatedFields | implemented with historical evidence | aligned-with-known-contract-note | Confirm Java/Python alias projection difference is still intentional or fixed. |
| Pivot 9.x | signed off v1.10 | aligned-with-accepted-risks | No immediate runtime work; keep deferred items gated. |
| Compose CTE basic | implemented | likely aligned | Needs current version test/evidence refresh. |
| Stable relation outer aggregate/window | contract mirror, not Python runtime | partial-by-design | Must not claim runtime parity unless implementation is approved. |
| Governance in query_model | implemented | needs-cross-path-matrix | Verify same behavior across base/timeWindow/pivot/compose. |
| SQL Server dialect evidence | mixed | accepted-refusal in Pivot; unknown for other paths | Build per-feature matrix. |
| MySQL 5.7 dialect evidence | mixed | accepted-refusal in Pivot; fallback in compose CTE | Build per-feature matrix. |

## Detailed Matrix

### Query Model Base

| Capability | Python Evidence | Status | Gap |
|---|---|---|---|
| field resolution `dim$prop`, id/caption | migration report says complete | aligned-likely | Needs current test count/evidence refresh. |
| auto JOIN / snowflake join | migration report says complete | aligned-likely | Needs current regression evidence. |
| inline aggregate expressions | migration report says complete | aligned-likely | Needs formula compiler parity refresh. |
| preAgg matcher | migration report says complete | aligned-likely | Need confirm current parity with Java latest if Java changed. |
| V3 metadata JSON/Markdown | migration report says complete | aligned-likely | Need current MCP schema/prompt alignment check. |

### CALCULATE / Formula

| Capability | Python Prompt Contract | Status | Gap |
|---|---|---|---|
| `CALCULATE(SUM(metric), REMOVE(groupByDim))` | public prompt documents restricted usage | partial-current | Must verify runtime supports only documented subset and fails closed outside it. |
| grouped aggregate window support | recent fix respected dialect feature flag | needs-audit | Need formal evidence across MySQL8/Postgres/SQLite and refusal for unsupported dialects. |
| `REMOVE` only removes current `groupBy` dim | prompt says restricted | needs-audit | Need tests proving non-grouped remove is rejected. |
| formula alias / orderBy interaction | historical timeWindow fix exists | needs-refresh | Need current formula compiler and field validator matrix. |

### timeWindow

| Capability | Python Evidence | Status | Gap |
|---|---|---|---|
| rolling / cumulative | v1.5 quality says implemented | aligned-with-refresh-needed | Re-run current tests and attach to v1.11. |
| comparative yoy/mom/wow | v1.5 quality says implemented, MySQL8 2025 seed evidence | aligned-with-refresh-needed | Re-run SQLite/MySQL8/Postgres; decide SQL Server status. |
| timeWindow + calculatedFields scalar post fields | v1.5 quality says implemented | aligned-with-known-risk | Need check Java/Python alias projection contract note. |
| timeWindow + pivot | prompt says rejected | aligned | Include schema/runtime rejection test in current matrix. |

### Pivot

| Capability | Python Status | Java Alignment |
|---|---|---|
| flat/grid base Pivot | signed off in v1.9 | aligned |
| Stage 5A DomainTransport SQLite/MySQL8/Postgres | signed off in v1.9/v1.10 | aligned |
| Stage 5B rows exactly two-level cascade | signed off in v1.9 | aligned |
| cascade subtotal/grandTotal additive surviving domain | signed off in v1.10 P1 | aligned with 9.2 follow-up closure |
| SQL Server cascade | accepted-refusal | aligned with fail-closed boundary, not parity |
| MySQL 5.7 cascade/large-domain | accepted-refusal | aligned with fail-closed boundary, not parity |
| tree + cascade | accepted-deferred | aligned with semantic-review-first boundary |
| outer Pivot cache | accepted-deferred | aligned with telemetry-first boundary |

### Compose / Stable Relation

| Capability | Python Evidence | Status | Gap |
|---|---|---|---|
| CTE composition | migration report says complete | aligned-likely | Needs current regression and MCP exposure check. |
| `compose_script` tool prompt | present | aligned-likely | Need runtime MCP e2e check. |
| Stable relation model / snapshots | v1.5 quality says mirror | contract-mirror | Not runtime parity. |
| outer aggregate / outer window over relation | Python intentionally no runtime | partial-by-design | Must decide whether to implement or keep mirror-only. |
| SQL Server CTE hoisting | documented risk | needs-audit | Confirm current fail-closed/fallback path. |

### Governance

| Path | Current Confidence | Required Evidence |
|---|---|---|
| base query_model | high | deniedColumns, systemSlice, masking, visible fields before SQL and after response. |
| timeWindow | medium | same permission tests after timeWindow lowering. |
| pivot | high | v1.9/v1.10 covered Pivot-specific paths. |
| compose | medium-low | verify compose does not bypass queryModel lifecycle or permission checks. |
| DomainTransport / cascade | high for supported dialects | existing v1.10 evidence plus one consolidated matrix. |

## Alignment Estimate

| View | Estimate | Reason |
|---|---:|---|
| Pivot-only alignment | 90%+ | Remaining items are explicit accepted-refusal/deferred, not unplanned gaps. |
| Core query_model alignment | 85-90% | Historical migration says mostly complete, but current evidence needs refresh. |
| Full engine runtime parity | 75-85% | Stable relation outer aggregate/window appears mirror-only in Python; compose/governance needs current proof. |
| Full engine contract parity | 85-90% | Most public contracts exist, but runtime-vs-mirror must be made explicit. |

These are audit estimates, not release claims. v1.11 must replace estimates with test-backed acceptance records.

## Highest-Value Next Work

1. CALCULATE / formula parity audit and cleanup.
2. timeWindow current-version evidence refresh.
3. compose/stable relation runtime boundary audit.
4. governance cross-path matrix.
5. v1.11 signoff with explicit runtime parity vs contract mirror labels.

## Decision

Python should not start new Pivot runtime features now.

The next implementation work should be gated by v1.11 parity audit phases. The most likely real gaps are non-Pivot: CALCULATE, timeWindow evidence refresh, compose stable relation runtime boundary, and governance consistency.
