---
doc_role: coverage-audit
doc_purpose: 盘点 v1.14 stable relation outer query SQL Server live oracle 的测试证据覆盖情况
status: signed-off
---

# Stable Relation Outer SQL Server Coverage Audit

## Document Purpose

- doc_type: coverage-audit
- intended_for: reviewer / test-owner / root-controller
- purpose: 确认 v1.14 对 SQL Server stable relation S7e/S7f runtime oracle 的证据是否足够进入签收。

## Coverage Matrix

| Requirement | Criticality | Coverage | Evidence |
|---|---|---|---|
| SQL Server inline relation can be outer aggregated | critical | covered | `test_outer_aggregate_groupby_oracle[sqlserver]` |
| SQL Server CTE relation can be hoisted with `;WITH` and outer aggregated | critical | covered | `test_outer_aggregate_cte_hoist_oracle[sqlserver]` |
| SQL Server CTE params are preserved in runtime execution | critical | covered | same test |
| SQL Server outer `RANK()` over derived ratio executes | critical | covered | `test_outer_window_rank_oracle[sqlserver]` |
| SQL Server outer moving average frame executes | critical | covered | `test_outer_window_moving_avg_oracle[sqlserver]` |
| Existing SQLite/MySQL8/PostgreSQL oracle evidence remains intact | critical | covered | same matrix, 16/16 total |
| Existing relation fail-closed unit coverage remains intact | critical | covered | `test_relation_outer_query_runtime.py` |

## Gaps

| Gap | Status | Reason |
|---|---|---|
| Public DSL E2E | not-applicable | Stable relation outer query remains an internal compiler API. |
| Relation join / union source | not-applicable | Not part of S7e/S7f outer aggregate/window runtime. |
| Pivot SQL Server cascade oracle | not-applicable | Pivot cascade SQL Server remains a separate accepted-refusal boundary. |

## Audit Conclusion

Coverage is sufficient for v1.14 acceptance. SQL Server stable relation outer query runtime is no longer marker-only for the covered S7e/S7f behaviors.
