# P3 Compose / Stable Relation Boundary Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: accepted-with-runtime-boundary
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 盘点 P3 compose/stable relation 边界签收的测试证据和剩余覆盖缺口。

## Coverage Map

| Requirement | Evidence | Status |
|---|---|---|
| Compose script can parse and build QueryPlan AST | `tests/compose/runtime/test_fsscript_e2e.py` | covered |
| QueryPlan `.to_sql()` / `.execute()` require runtime bundle and preserve route_model | `tests/compose/runtime/test_plan_execution.py` | covered |
| Compile errors propagate, execute errors are tagged execute phase | `tests/compose/runtime/test_plan_execution.py` | covered |
| FSScript sandbox and fluent API stay locked down | `tests/compose/**` | covered |
| MCP `compose_script` public tool executes normal path | `tests/test_mcp/test_compose_script_tool_binding.py` | covered |
| Remote authority envelope applies systemSlice | `test_odoo_remote_compose_normal_path` | covered |
| Remote authority envelope blocks denied columns and malformed bindings | `test_odoo_remote_compose_denied_columns_blocks_query`, related cases | covered |
| Stable relation S7a Java snapshot compatibility | `test_stable_relation_snapshot.py` | covered |
| Stable relation S7e outer aggregate contract compatibility | `test_stable_relation_outer_aggregate_snapshot.py` | contract-covered |
| Stable relation S7f outer window contract compatibility | `test_stable_relation_outer_window_snapshot.py` | contract-covered |
| SQL Server hoisted CTE markers | S7e/S7f snapshot cases | contract-covered |
| MySQL 5.7 relation refusal | S7e/S7f snapshot cases | contract-covered |

## Commands

```powershell
pytest tests\compose -q -rs
pytest tests\test_mcp\test_compose_script_tool_binding.py -q -rs
pytest tests\compose\relation\test_stable_relation_snapshot.py tests\compose\relation\test_stable_relation_outer_aggregate_snapshot.py tests\compose\relation\test_stable_relation_outer_window_snapshot.py -q -rs
pytest tests\compose\runtime\test_plan_execution.py tests\compose\runtime\test_fsscript_e2e.py -q -rs
```

Observed results:

- `1146 passed`
- `10 passed`
- `70 passed`
- `44 passed`

## Coverage Gaps

| Gap | Impact | Disposition |
|---|---|---|
| No Python live DB oracle for stable relation outer aggregate/window | Cannot claim runtime parity with Java S7e/S7f | accepted boundary |
| SQL Server relation wrapping is snapshot-level only | No Python runtime proof for hoisted CTE execution | accepted boundary |
| MySQL 5.7 relation wrapper refusal is snapshot-level only | No live MySQL 5.7 evidence | accepted boundary |
| Governance across base/timeWindow/pivot/compose not consolidated in one matrix | Need cross-path confidence before version signoff | P4 required |

## Audit Decision

Coverage is sufficient for P3 `accepted-with-runtime-boundary`.

Coverage is not sufficient to claim full stable relation runtime parity.
