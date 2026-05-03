# P3 Compose / Stable Relation Boundary Acceptance

## 文档作用

- doc_type: acceptance
- status: accepted-with-runtime-boundary
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 签收 Python 当前 compose_script 与 stable relation 边界，明确哪些能力是运行时对齐，哪些只是 Java contract mirror。

## Scope

本次验收覆盖：

- Compose Query script 解析、sandbox、plan AST、compile-to-SQL、execute_sql 路由。
- MCP `compose_script` tool binding 与 Odoo remote authority envelope。
- Stable relation S7a/S7e/S7f dataclass、capability matrix、error code 与 Java snapshot 消费。
- SQL Server CTE hoisting / MySQL 5.7 fail-closed 的合同证据。

不在本次验收范围：

- 在 Python 运行时实现 Java stable relation outer aggregate / outer window 编译执行。
- 扩展 public DSL。
- 用 compose_script 绕过 query_model 生命周期或权限绑定。

## Decision

Decision: `accepted-with-runtime-boundary`.

Python 当前可以签收：

- Basic compose runtime: `accepted`.
- Public `compose_script` MCP path: `accepted`.
- Stable relation model/capability/error contract: `accepted`.
- Stable relation outer aggregate/window runtime: `contract-mirror-only`，不得宣称 Python runtime parity。

这不是阻断 Python v1.11 的问题，但必须在 version signoff 中保留为显式边界。

## Capability Matrix

| Capability | Python Status | Evidence | Boundary |
|---|---|---|---|
| Compose script parser / sandbox / QueryPlan AST | accepted | `tests/compose` | Runtime implemented. |
| QueryPlan compile + execute_sql route_model | accepted | `tests/compose/runtime/test_plan_execution.py` | Runtime implemented. |
| FSScript fluent API E2E | accepted | `tests/compose/runtime/test_fsscript_e2e.py` | Runtime implemented. |
| MCP `compose_script` remote envelope | accepted | `tests/test_mcp/test_compose_script_tool_binding.py` | Runtime implemented with permission envelope checks. |
| Stable relation S7a contract | accepted | `test_stable_relation_snapshot.py` | Contract mirror. |
| Stable relation outer aggregate S7e | accepted-contract | `test_stable_relation_outer_aggregate_snapshot.py` | Python mirrors Java snapshot/capability only. |
| Stable relation outer window S7f | accepted-contract | `test_stable_relation_outer_window_snapshot.py` | Python mirrors Java snapshot/capability only. |
| SQL Server hoisted CTE relation | accepted-contract | S7e/S7f snapshot cases | Contract mirror; runtime path not claimed. |
| MySQL 5.7 relation wrapper refusal | accepted-contract | S7e/S7f snapshot cases | Fail-closed contract mirror. |

## Test Evidence

Commands run on 2026-05-03:

```powershell
pytest tests\compose -q -rs
```

Result:

```text
1146 passed in 1.54s
```

```powershell
pytest tests\test_mcp\test_compose_script_tool_binding.py -q -rs
```

Result:

```text
10 passed in 0.30s
```

```powershell
pytest tests\compose\relation\test_stable_relation_snapshot.py tests\compose\relation\test_stable_relation_outer_aggregate_snapshot.py tests\compose\relation\test_stable_relation_outer_window_snapshot.py -q -rs
```

Result:

```text
70 passed in 0.12s
```

```powershell
pytest tests\compose\runtime\test_plan_execution.py tests\compose\runtime\test_fsscript_e2e.py -q -rs
```

Result:

```text
44 passed in 0.06s
```

## Accepted Risks

- Python has no signed runtime implementation for Java stable relation outer aggregate/window as of v1.11 P3.
- Existing S7e/S7f Python tests validate Java snapshot compatibility and capability flags, not live DB execution of relation outer wrapping.
- A future runtime parity implementation must produce separate SQLite/MySQL8/PostgreSQL/SQL Server oracle evidence before the boundary can be upgraded.

## Follow-Up

- Keep P4 governance cross-path matrix as next required v1.11 phase.
- If product requires full stable relation runtime parity, create a dedicated P5+ implementation plan instead of folding it into P3 evidence refresh.
