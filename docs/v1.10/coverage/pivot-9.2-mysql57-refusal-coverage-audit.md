# Pivot 9.2 MySQL 5.7 Refusal Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: passed
- intended_for: coverage-auditor / signoff-owner
- purpose: 盘点 Python Pivot v1.10 P3 MySQL 5.7 refusal 的需求、测试证据和剩余风险。

## Coverage Matrix

| Requirement | Evidence | Status |
|---|---|---|
| `mysql5.7` C2 cascade rejects | `test_mysql57_cascade_refuses_before_sql_execution` | covered |
| refusal uses stable cascade error code | same test asserts `PIVOT_CASCADE_SQL_REQUIRED` | covered |
| refusal happens before SQL execution | fail-if-called executor remains unused | covered |
| `mysql5.7` large-domain transport rejects | `test_mysql57_large_domain_transport_refuses_at_build_time` | covered |
| refusal uses stable domain transport error code | same test asserts `PIVOT_DOMAIN_TRANSPORT_REFUSED` | covered |
| MySQL8 profile not relabeled as MySQL 5.7 | existing MySQL8 cascade/domain transport tests remain separate | covered by prior matrix |

## Commands

```powershell
pytest tests/integration/test_pivot_v9_cascade_mysql57_matrix.py -q -rs
```

Result:

```text
2 passed in 0.25s
```

Regression commands:

```powershell
pytest tests/integration/test_pivot_v9_cascade_mysql57_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/test_dataset_model/test_pivot_v9_domain_transport.py -q -rs
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
pytest -q
```

Results:

```text
34 passed in 0.28s
30 passed in 3.26s
3942 passed in 16.18s
```

## Remaining Gaps

- No live MySQL 5.7 container/profile is available in Python CI.
- No MySQL 5.7 oracle parity is claimed.
- Any future support must prove a different execution strategy because C2 cascade depends on ranking windows.

Coverage conclusion: P3 has sufficient refusal evidence for acceptance; it does not claim MySQL 5.7 runtime parity.
