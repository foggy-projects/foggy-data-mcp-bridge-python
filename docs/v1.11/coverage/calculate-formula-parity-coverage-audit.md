# CALCULATE / Formula Parity Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: passed
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 盘点 v1.11 P1 CALCULATE / formula parity 的需求、测试和证据映射，确认是否可进入验收。

## Requirement Mapping

| Requirement | Test Evidence | Status |
|---|---|---|
| compiler lowers supported CALCULATE to grouped aggregate window | `test_calculate_mvp_parity_catalog.py` | covered |
| service build path carries calculate context from `groupBy` | `test_calculate_mvp_service.py` | covered |
| SQLite executed result equals handwritten SQL oracle | `test_calculate_mvp_real_db_matrix.py` | covered |
| MySQL 8 executed result equals handwritten SQL oracle | `test_calculate_mvp_real_db_matrix.py` | covered |
| PostgreSQL executed result equals handwritten SQL oracle | `test_calculate_mvp_real_db_matrix.py` | covered |
| missing `NULLIF(CALCULATE(...), 0)` guard is rejected | catalog | covered |
| remove non-grouped field rejected | catalog | covered |
| remove system-sliced field rejected | catalog | covered |
| nested CALCULATE rejected | catalog | covered |
| timeWindow post-calc CALCULATE rejected | catalog | covered |
| conservative MySQL profile rejected | service test | covered |
| MCP prompt documents the restricted subset | `test_query_model_calculate_prompt.py` | covered |

## Test Commands

```powershell
pytest tests/test_dataset_model/test_calculate_mvp_service.py tests/test_dataset_model/test_calculate_mvp_parity_catalog.py tests/test_mcp/test_query_model_calculate_prompt.py tests/integration/test_calculate_mvp_real_db_matrix.py -q -rs
```

Result:

```text
19 passed in 0.62s
```

## Coverage Notes

- The parity catalog is now stored inside this Python repository at `docs/v1.5.1/P1-CALCULATE-restricted-mvp-parity-catalog.json`. The previous test path depended on the parent workspace and was not portable.
- MySQL 8 oracle tests use the explicit `MySql8Dialect` profile. Default `mysql` remains conservative and fail-closed.
- This audit does not claim parity for arbitrary CALCULATE, MDX tuple navigation, or nested coordinate references.

## Decision

Coverage is sufficient for P1 acceptance.
