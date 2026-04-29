# S7 CTE / timeWindow capability recap

## Document Purpose

- doc_type: capability-recap
- intended_for: root-controller / Java contract owner / Python mirror owner / reviewer
- purpose: 在 S7 签收后，复盘 CTE 与 timeWindow 相关能力的当前对齐状态、明确非目标和后续关注点。

## Current Decision

- S7 status: signed off with accepted risks.
- Signoff record: `docs/v1.5/acceptance/S7-stage7-acceptance.md`.
- Coverage record: `docs/v1.5/coverage/S7-stage7-coverage-audit.md`.
- S8 relation join / union / in-memory post-processing: not started.
- Current follow-up focus: CTE and timeWindow capability recap, not new runtime expansion.

## CTE Capability Status

| Capability | Java | Python | Status | Notes |
|---|---|---|---|---|
| Internal generated CTE for complex compose / timeWindow SQL | supported | supported in existing compiler paths | aligned | Used as compiler-generated physical SQL structure, not user-authored named CTE. |
| Stable relation wrapping with inner CTE | supported | model / snapshot consumer mirror | aligned at contract level | Java runtime owns SQL generation; Python verifies Java snapshots. |
| SQL Server top-level hoisted CTE | supported | executor / contract mirror support | aligned for current contract | Hard rule: never generate `FROM (WITH ... SELECT ...) AS rel`. |
| SQL Server defensive `;WITH` | supported where hoisting is emitted | mirrored in snapshot checks | aligned | Prevents T-SQL statement-boundary ambiguity. |
| MySQL 5.7 + inner CTE | fail-closed | fail-closed in capability mirror | aligned | Do not silently emit invalid SQL. |
| Parameter flattening across CTE + body + outer query | covered by Java tests / snapshots | snapshot consumer checks | aligned for S7 | Future token-level diff can strengthen this further. |
| Explicit user named CTE | not supported | not supported | deferred | Requires scope, collision, permission, and dialect rules. |
| Recursive CTE | not supported | not supported | deferred | Not part of v1.4/v1.5 or S7. |
| Token-by-token normalized diff for multi-CTE SQL | partial | partial | deferred | Current proof uses structured snapshots and forbidden-marker assertions because Java/Python SQL architecture can differ. |

## timeWindow Capability Status

| Capability | Java | Python | Status | Notes |
|---|---|---|---|---|
| Core timeWindow CTE / derived SQL generation | supported | supported | aligned | Prior v1.4/v1.5 parity and real DB matrix cover core behavior. |
| Comparative windows such as yoy / mom / wow | supported | supported | aligned | Includes real DB coverage and fixture parity. |
| Rolling and cumulative windows such as rolling / YTD / MTD | supported | supported | aligned | SQL Server real DB matrix was added for this lane. |
| `timeWindow + calculatedFields` post scalar projection | supported | supported | aligned | Signed off separately in `P1-timeWindow-calculatedFields-acceptance.md`. |
| Request columns can reference allowed post calculatedFields names | supported | supported | aligned | Java alias validator extension is complete; plain `amount AS amount1` remains closed. |
| `calculatedFields` as `targetMetrics` input | rejected | rejected | aligned closed | Prevents circular or unstable metric definitions. |
| Post-timeWindow calculatedField aggregate | rejected in timeWindow channel | rejected in timeWindow channel | aligned closed | S7 moves second-stage aggregation to relation outer aggregate instead. |
| Post-timeWindow calculatedField window | rejected in timeWindow channel | rejected in timeWindow channel | aligned closed | S7 moves second-stage windowing to relation outer window instead. |
| Stable output schema for timeWindow derived columns | supported via `CompiledRelation` | mirrored from Java snapshots | aligned at S7 contract level | Derived columns carry semantic metadata and reference policy. |

## Relation Layer Interpretation

The accepted model is:

```text
QueryPlan / timeWindow plan
  -> stable CompiledRelation
  -> optional outer read / aggregate / window query
```

This means second-stage analytics should not be modeled as more `timeWindow + calculatedFields` syntax inside the same DSL request. The stable relation layer provides the output schema boundary that humans and LLMs can reason about before adding outer operations.

## Accepted Risks

- Python runtime does not implement outer aggregate / outer window. It remains a mirror and Java snapshot consumer for S7.
- S8 relation join / union and in-memory post-processing are not started.
- Explicit named CTE and recursive CTE remain future contract items.
- Multi-CTE token-level golden diff remains deferred; current evidence is structural and snapshot-based.

## Next Review Focus

1. Keep S8 closed unless a concrete downstream workflow requires relation composition.
2. Review CTE/timeWindow docs for stale statements after S7 signoff.
3. If more verification is needed, prefer strengthening multi-CTE normalized SQL diff harness before adding new runtime features.
