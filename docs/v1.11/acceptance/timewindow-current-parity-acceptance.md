# timeWindow Current Parity Acceptance

## 文档作用

- doc_type: acceptance
- status: accepted
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 签收 v1.11 P2 timeWindow 当前版本证据刷新，确认历史 v1.5 能力在当前 main 上仍与 Java 已签收子集对齐。

## Scope

本次 P2 是 evidence refresh，不新增 public DSL，也不扩大 runtime 范围。

覆盖能力：

- Java camelCase `timeWindow` payload passthrough。
- validator error code / grain / comparison / range / targetMetrics。
- rolling 7d。
- cumulative `mtd` / `ytd`。
- comparative `yoy` / `mom` / `wow`。
- timeWindow 输出列上的后置 scalar `calculatedFields`。
- `timeWindow + pivot` fail-closed。
- SQLite / MySQL8 / PostgreSQL / SQL Server real DB execution matrix。

## Accepted Behavior

| Behavior | Decision | Evidence |
|---|---|---|
| `timeWindow` request serialization uses Java `timeWindow` alias | accepted | `test_java_alignment.py` |
| rolling / cumulative / comparative validator matrix | accepted | `test_time_window.py` |
| SQLite execution with exact expected rows | accepted | `test_time_window_sqlite_execution.py` |
| Java fixture SQL contract | accepted | `test_time_window_java_parity_catalog.py` |
| MySQL8 / PostgreSQL / SQL Server execution smoke and semantic checks | accepted | `test_time_window_real_db_matrix.py` |
| post scalar calculatedFields over timeWindow output | accepted | SQLite + real DB matrix |
| `timeWindow + pivot` | fail-closed | Pivot contract/runtime tests |
| post calc with aggregate/window semantics | fail-closed/deferred | v1.5 contract remains active |

## Evidence

Commands run:

```powershell
pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/integration/test_time_window_real_db_matrix.py tests/test_mcp/test_java_alignment.py -q -rs
```

Result:

```text
111 passed in 0.99s
```

Additional `timeWindow + pivot` fail-closed confirmation:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_flat.py::test_flat_pivot_rejects_time_window_at_runtime tests/test_dataset_model/test_pivot_v9_contract_shell.py -q
```

Result:

```text
7 passed in 0.28s
```

## Decision

P2 timeWindow current parity is accepted.

Remaining v1.11 work moves to P4 governance cross-path matrix.
