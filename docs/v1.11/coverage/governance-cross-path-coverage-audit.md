# P4 Governance Cross-Path Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: accepted
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 盘点 P4 governance 横向矩阵的测试覆盖，确认是否可进入 v1.11 version signoff。

## Coverage Map

| Requirement | Evidence | Status |
|---|---|---|
| `deniedColumns` physical-to-QM mapping | `test_physical_column_governance.py` | covered |
| denied measure/dimension/orderBy/slice/calculatedFields fail closed | `test_physical_column_governance.py` | covered |
| `fieldAccess.visible` whitelist validation | `test_column_governance.py` | covered |
| response column filtering | `test_column_governance.py` | covered |
| masking functions and service post-processing | `test_column_governance.py` | covered |
| `systemSlice` bypasses field validation but merges into SQL | `test_physical_column_governance.py` | covered |
| metadata v3 denied trimming | `test_physical_column_governance.py`, `test_metadata_v3_cross_model_governance.py` | covered |
| timeWindow systemSlice / deniedColumns / masking | `test_time_window_sqlite_execution.py` | covered |
| pivot systemSlice and deniedColumns | `test_pivot_v9_flat.py` | covered |
| Pivot DomainTransport deniedColumns | `test_pivot_v9_domain_transport_query_model.py` | covered |
| compose authority envelope validation | `test_compose_script_tool_binding.py`, `tests/compose/authority` | covered |
| compose plan-aware fieldAccess validation | `tests/compose/security` | covered |
| MCP router forwards governance payloads | `test_mcp_rpc_router.py` | covered |

## Commands

```powershell
pytest tests\test_column_governance.py tests\test_physical_column_governance.py tests\test_metadata_v3_cross_model_governance.py tests\test_dataset_model\test_time_window_sqlite_execution.py tests\test_dataset_model\test_pivot_v9_flat.py tests\test_dataset_model\test_pivot_v9_domain_transport_query_model.py tests\test_mcp\test_compose_script_tool_binding.py -q -rs
pytest tests\test_mcp\test_mcp_rpc_router.py tests\compose\authority tests\compose\security -q -rs
```

Observed results:

- `215 passed`
- `120 passed`

## Remaining Coverage Boundaries

| Boundary | Reason | Disposition |
|---|---|---|
| stable relation outer aggregate/window runtime governance | P3 labels this as contract mirror only | not required for v1.11 |
| SQL Server live governance matrix for compose outer relation | no runtime outer relation claim | not required |
| masking in compose result rows | compose primarily verifies authority/permission compile path; masking is query_model response post-processing | accepted boundary |

## Audit Decision

Coverage is sufficient for P4 acceptance and v1.11 version signoff.
