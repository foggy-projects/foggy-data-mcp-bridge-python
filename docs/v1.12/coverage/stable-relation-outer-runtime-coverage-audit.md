---
doc_role: coverage-audit
doc_purpose: 盘点 v1.12 stable relation outer aggregate/window runtime 的测试证据覆盖情况
status: signed-off
---

# Stable Relation Outer Runtime Coverage Audit

## Document Purpose

- doc_type: coverage-audit
- intended_for: reviewer / test-owner / root-controller
- purpose: 确认 v1.12 P1 stable relation runtime 对 Java S7e/S7f 的关键语义是否有测试证据。

## Coverage Matrix

| Requirement | Criticality | Coverage | Evidence |
|---|---|---|---|
| Inline relation can be wrapped and outer aggregated | critical | covered | `test_outer_aggregate_executes_sqlite_oracle` |
| Relation with inner CTE is hoisted before outer aggregate | critical | covered | `test_outer_aggregate_hoists_cte_and_preserves_param_order` |
| Parameter order is CTE params then body params | critical | covered | same as above |
| Non-aggregatable ratio/timeWindow field is rejected | critical | covered | `test_outer_aggregate_rejects_non_aggregatable_ratio` |
| MySQL 5.7 + CTE relation fails closed | critical | covered | `test_outer_aggregate_rejects_mysql57_cte_relation` |
| Outer window can rank by orderable ratio without using it as input | critical | covered | `test_outer_window_rank_executes_sqlite_oracle_with_ratio_order_key` |
| Outer window can calculate moving average over windowable measure | critical | covered | `test_outer_window_moving_avg_executes_sqlite_oracle` |
| Non-windowable ratio input is rejected | critical | covered | `test_outer_window_rejects_ratio_as_window_input` |
| MySQL 5.7 outer window fails closed | critical | covered | `test_outer_window_rejects_mysql57_even_without_cte` |
| SQL Server CTE hoist marker avoids `FROM (WITH` | major | covered | `test_outer_window_sqlserver_hoists_cte_without_from_with_marker` |

## Gaps

| Gap | Status | Reason |
|---|---|---|
| Live MySQL8/PostgreSQL stable relation execution | not-covered | The Java S7e/S7f contract was snapshot-oriented; Python P1 proves runtime through SQLite and dialect markers. |
| SQL Server live execution | not-covered | Existing Java/Python contract checks marker and hoist shape; live SQL Server oracle remains out of scope. |
| Public DSL E2E | not-applicable | This is an internal compiler API, not a public DSL expansion. |

## Audit Conclusion

Targeted coverage is sufficient for feature acceptance. Relation focused suite and full regression both passed:

```powershell
pytest tests/compose/relation -q -rs
# 106 passed in 0.15s

pytest -q
# 3961 passed in 12.14s
```
