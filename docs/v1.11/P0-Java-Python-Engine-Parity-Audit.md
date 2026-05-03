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
| CALCULATE / REMOVE | accepted-with-profile-note | aligned-for-restricted-subset | Restricted public subset has SQLite/MySQL8/PostgreSQL oracle; default mysql profile remains fail-closed. |
| timeWindow | accepted-current | aligned | v1.11 P2 reran current evidence matrix across SQLite/MySQL8/PostgreSQL/SQL Server. |
| timeWindow + calculatedFields | accepted-current | aligned-for-post-scalar-subset | Post scalar subset remains accepted; outer aggregate/window stays deferred to relation layer. |
| Pivot 9.x | signed off v1.10 | aligned-with-accepted-risks | No immediate runtime work; keep deferred items gated. |
| Compose CTE basic | accepted | aligned | Current compose runtime tests passed. |
| Stable relation outer aggregate/window | accepted-contract | partial-by-design | Contract mirror only; do not claim Python runtime parity. |
| Governance in query_model | accepted | aligned | Cross-path matrix passed for base/timeWindow/pivot/compose/MCP router. |
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
| `CALCULATE(SUM(metric), REMOVE(groupByDim))` | public prompt documents restricted usage | accepted | `calculate-formula-parity-acceptance.md` |
| grouped aggregate window support | explicit dialect capability flag | accepted-with-profile-note | SQLite/MySQL8/Postgres oracle; conservative mysql profile refused. |
| `REMOVE` only removes current `groupBy` dim | prompt says restricted | accepted | catalog rejects non-grouped remove and system-slice override. |
| formula alias / orderBy interaction | historical timeWindow fix exists | needs-refresh | Broader formula/orderBy matrix remains outside P1. |

### timeWindow

| Capability | Python Evidence | Status | Gap |
|---|---|---|---|
| rolling / cumulative | current v1.11 evidence | accepted | `timewindow-current-parity-acceptance.md` |
| comparative yoy/mom/wow | current v1.11 evidence | accepted | MySQL8/PostgreSQL/SQL Server real DB matrix passed. |
| timeWindow + calculatedFields scalar post fields | current v1.11 evidence | accepted-for-post-scalar-subset | SQLite + real DB matrix passed; agg/window remains deferred. |
| timeWindow + pivot | prompt says rejected | accepted-fail-closed | Runtime/schema rejection tests passed. |

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
| CTE composition | current tests passed | accepted | `tests/compose` passed. |
| `compose_script` tool prompt | current MCP tests passed | accepted | Remote authority envelope and denied columns covered. |
| Stable relation model / snapshots | current snapshot tests passed | accepted-contract | Java S7a/S7e/S7f snapshots consumed. |
| outer aggregate / outer window over relation | contract mirror only | partial-by-design | Runtime parity not claimed. |
| SQL Server CTE hoisting | snapshot contract covered | accepted-contract | S7e/S7f hoisted CTE markers covered; runtime not claimed. |

### Governance

| Path | Current Confidence | Required Evidence |
|---|---|---|
| base query_model | accepted | deniedColumns, systemSlice, masking, visible fields before SQL and after response. |
| timeWindow | accepted | systemSlice, deniedColumns, masking tests added in P4. |
| pivot | accepted | flat Pivot and DomainTransport governance evidence passed. |
| compose | accepted | remote authority envelope, denied columns, malformed binding, fieldAccess security tests passed. |
| DomainTransport / cascade | accepted | DomainTransport deniedColumns and existing Pivot evidence retained. |

## Alignment Estimate

| View | Estimate | Reason |
|---|---:|---|
| Pivot-only alignment | 90%+ | Remaining items are explicit accepted-refusal/deferred, not unplanned gaps. |
| Core query_model alignment | 85-90% | Historical migration says mostly complete, but current evidence needs refresh. |
| Full engine runtime parity | 85-90% | P1-P4 current evidence is signed off; stable relation outer aggregate/window remains mirror-only. |
| Full engine contract parity | 90-93% | P1-P4 contracts are refreshed and version-level signoff is complete; future stable relation runtime expansion remains optional. |

These are audit estimates, not MDX or full Java runtime parity claims. v1.11 replaces the original estimates with test-backed acceptance records and explicit runtime-vs-contract boundaries.

## Highest-Value Next Work

1. v1.11 signoff with explicit runtime parity vs contract mirror labels.
2. Optional future stable relation runtime parity plan if product requires it.

## Decision

Python should not start new Pivot runtime features now.

CALCULATE P1, timeWindow P2, compose/stable relation P3, and governance P4 are accepted for their signed-off subsets. v1.11 version-level signoff is complete. Further runtime expansion, especially stable relation outer aggregate/window execution parity, requires a separate product requirement and test plan.

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: root-controller
- signed_off_at: 2026-05-03
- acceptance_record: docs/v1.11/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: yes
