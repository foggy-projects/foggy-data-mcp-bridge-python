# P4 Governance Cross-Path Acceptance

## 文档作用

- doc_type: acceptance
- status: accepted
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 签收 Python engine 当前 `systemSlice`、`deniedColumns`、`fieldAccess`、masking 在 base query_model、timeWindow、pivot、compose 路径上的一致性证据。

## Scope

本次验收覆盖：

- base query_model 的 pre-SQL field governance、systemSlice merge、post-response visible filtering/masking。
- timeWindow lowering 前后的 governance 顺序。
- pivot translation 后的 governance，以及 DomainTransport / size fallback 不能绕过 deniedColumns。
- compose_script remote authority envelope 到 per-base query request 的权限传递。
- MCP router 对 `visibleFields`、`deniedColumns`、`systemSlice` 的参数透传。

不在本次验收范围：

- 新权限模型设计。
- 字段级脱敏策略扩展。
- stable relation outer aggregate/window runtime governance，因为 P3 已明确为 contract mirror only。

## Decision

Decision: `accepted`.

Python 当前 governance 横向矩阵可以签收：

- query_model base path: accepted.
- timeWindow path: accepted.
- pivot path: accepted.
- compose_script path: accepted.
- metadata visibility trimming: accepted.

## Cross-Path Matrix

| Path | systemSlice | deniedColumns | fieldAccess visible | masking | Evidence |
|---|---|---|---|---|---|
| base query_model | accepted | accepted | accepted | accepted | `test_column_governance.py`, `test_physical_column_governance.py` |
| metadata v3 | n/a | accepted | accepted | n/a | `test_physical_column_governance.py`, `test_metadata_v3_cross_model_governance.py` |
| timeWindow | accepted | accepted | inherited via validation | accepted | `test_time_window_sqlite_execution.py` |
| pivot flat/grid | accepted | accepted | inherited via translated request | inherited post-shape | `test_pivot_v9_flat.py` |
| Pivot DomainTransport | accepted | accepted | inherited via base request | inherited post-query | `test_pivot_v9_domain_transport_query_model.py` |
| compose_script | accepted | accepted | accepted by compose authority/security layers | not separately expanded | `test_compose_script_tool_binding.py`, `tests/compose/authority`, `tests/compose/security` |
| MCP router | forwarded | forwarded | forwarded | n/a | `test_mcp_rpc_router.py` |

## New Evidence Added

P4 added direct timeWindow governance tests:

- `test_time_window_system_slice_applies_to_base_cte`
- `test_time_window_denied_columns_fail_closed`
- `test_time_window_masking_applies_after_execution`

These close the previous direct-evidence gap where timeWindow governance was inferred from base query_model.

## Test Evidence

Commands run on 2026-05-03:

```powershell
pytest tests\test_column_governance.py tests\test_physical_column_governance.py tests\test_metadata_v3_cross_model_governance.py tests\test_dataset_model\test_time_window_sqlite_execution.py tests\test_dataset_model\test_pivot_v9_flat.py tests\test_dataset_model\test_pivot_v9_domain_transport_query_model.py tests\test_mcp\test_compose_script_tool_binding.py -q -rs
```

Result:

```text
215 passed in 0.93s
```

```powershell
pytest tests\test_mcp\test_mcp_rpc_router.py tests\compose\authority tests\compose\security -q -rs
```

Result:

```text
120 passed in 0.55s
```

```powershell
pytest tests\test_dataset_model\test_time_window_sqlite_execution.py -q -rs
```

Result:

```text
8 passed in 0.34s
```

## Accepted Boundary

- `systemSlice` bypasses user-visible field validation by design but is merged into SQL filters before execution.
- User-provided `slice`, `columns`, `orderBy`, `calculatedFields`, and pivot-translated axes remain subject to denied/visible governance.
- Compose uses its authority envelope and per-base query compilation path; it must not accept host-controlled `systemSlice` / `deniedColumns` from script text.

## Follow-Up

P1-P4 are now signed off. The next phase is v1.11 version signoff with explicit labels for:

- runtime parity,
- contract mirror,
- accepted refusal,
- deferred future work.
