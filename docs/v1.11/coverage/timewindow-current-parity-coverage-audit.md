# timeWindow Current Parity Coverage Audit

## 文档作用

- doc_type: coverage-audit
- status: passed
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 盘点 v1.11 P2 timeWindow 当前版本证据刷新覆盖面，确认是否可进入验收。

## Requirement Mapping

| Requirement | Evidence | Status |
|---|---|---|
| `timeWindow` camelCase payload and nested key passthrough | `test_java_alignment.py` | covered |
| validator mirrors Java error code matrix | `test_time_window.py` | covered |
| relative / compact date parsing | `test_time_window.py` | covered |
| rolling window IR and SQL lowering | `test_time_window.py`, `test_time_window_sqlite_execution.py` | covered |
| cumulative `mtd` / `ytd` SQL execution | `test_time_window_real_db_matrix.py` | covered |
| comparative `yoy` / `mom` / `wow` SQL execution | `test_time_window_real_db_matrix.py` | covered |
| SQLite exact-row execution | `test_time_window_sqlite_execution.py` | covered |
| Java fixture SQL contract | `test_time_window_java_parity_catalog.py` | covered |
| MySQL8 real DB execution | `test_time_window_real_db_matrix.py` | covered |
| PostgreSQL real DB execution | `test_time_window_real_db_matrix.py` | covered |
| SQL Server real DB execution | `test_time_window_real_db_matrix.py` | covered |
| post scalar calculatedFields | SQLite + real DB matrix | covered |
| post scalar calculatedFields alias orderBy | `test_time_window_sqlite_execution.py` | covered |
| `timeWindow + pivot` rejected | pivot runtime + schema contract tests | covered |

## Test Commands

```powershell
pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/integration/test_time_window_real_db_matrix.py tests/test_mcp/test_java_alignment.py -q -rs
```

Result:

```text
111 passed in 0.99s
```

```powershell
pytest tests/test_dataset_model/test_pivot_v9_flat.py::test_flat_pivot_rejects_time_window_at_runtime tests/test_dataset_model/test_pivot_v9_contract_shell.py -q
```

Result:

```text
7 passed in 0.28s
```

## Coverage Notes

- The v1.5 coverage record originally treated MySQL8/PostgreSQL as local/manual evidence. The current v1.11 refresh uses automated integration tests and includes SQL Server in the same command.
- This P2 does not add a Java-vs-Python cross-process golden runner. It uses existing Java fixture catalog plus executed DB matrix as the current acceptance basis.
- `timeWindow + calculatedFields` remains limited to post scalar expressions over timeWindow output columns.

## Decision

Coverage is sufficient for P2 acceptance.
