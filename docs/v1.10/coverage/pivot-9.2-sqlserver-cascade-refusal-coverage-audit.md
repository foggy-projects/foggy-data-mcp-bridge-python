# Pivot 9.2 SQL Server Cascade Refusal Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: passed
- intended_for: coverage-auditor / signoff-owner
- purpose: 盘点 Python Pivot v1.10 P2 SQL Server cascade refusal 的需求、测试证据和剩余风险。

## Coverage Matrix

| Requirement | Evidence | Status |
|---|---|---|
| explicit SQL Server dialect refuses C2 cascade | `test_sqlserver_cascade_refuses_with_explicit_dialect_before_sql_execution` | covered |
| `SQLServerExecutor` route infers SQL Server dialect | `test_sqlserver_cascade_refuses_with_executor_inferred_dialect_before_connection` | covered |
| refusal happens before executor SQL execution | both SQL Server tests use fail-if-called executor hooks | covered |
| stable error code returned | both tests assert `PIVOT_CASCADE_SQL_REQUIRED` | covered |
| existing unsupported dialect semantic test remains green | `test_unsupported_dialect_fallback_rejection` | covered |
| no SQLite/MySQL8/PostgreSQL cascade regression | `test_pivot_v9_cascade_validation.py` + `test_pivot_v9_cascade_real_db_matrix.py` + SQL Server refusal matrix | covered |

## Commands

```powershell
pytest tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py -q -rs
```

Result:

```text
8 passed in 0.48s
```

Regression command:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py -q -rs
```

Result:

```text
32 passed in 1.38s
```

Full regression:

```powershell
pytest -q
```

Result:

```text
3940 passed in 11.51s
```

## Remaining Gaps

- SQL Server C2 cascade oracle parity remains unsupported.
- SQL Server-specific staged SQL renderer remains unimplemented.
- SQL Server NULL-safe tuple matching and quote strategy remain unsigned.
- MySQL 5.7 live/refusal evidence remains P3.

Coverage conclusion: P2 has sufficient refusal evidence for acceptance; it does not claim SQL Server runtime parity.
