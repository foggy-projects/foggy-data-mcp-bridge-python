# Pivot 9.2 SQL Server Cascade Refusal Acceptance

## 文档作用

- doc_type: feature-acceptance
- status: accepted-refusal
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 Python Pivot v1.10 P2 SQL Server cascade 的方言结论、拒绝证据和签收边界。

## Scope

P2 不实现 SQL Server C2 cascade staged SQL。P2 的目标是为 SQL Server 建立明确的 runtime evidence：

- SQL Server cascade 不进入未验证 SQL 生成。
- SQL Server cascade 不回退到内存 ranking/filtering。
- SQL Server cascade 返回稳定 `PIVOT_CASCADE_SQL_REQUIRED` 错误。
- 普通 SQLite/MySQL8/PostgreSQL cascade parity 不受影响。

不改变 public Pivot DSL，不新增 schema 字段，不声明 SQL Server cascade oracle parity。

## Decision

Status: accepted-refusal.

SQL Server 暂不支持 Python C2 cascade，原因：

- `DomainRelationRenderer` 尚无 SQL Server renderer。
- SQL Server NULL-safe tuple matching shape 尚未签收。
- staged CTE 中的 identifier quoting、`ROW_NUMBER` tie-breaker 与 params order 尚未通过真实 SQL Server oracle。
- 在这些证据完成前，任何 SQL Server cascade 运行都必须 fail-closed。

## Evidence

Targeted P2 command:

```powershell
pytest tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py -q -rs
```

Result:

```text
8 passed in 0.48s
```

The SQL Server refusal matrix uses the real `SqlServerDialect` and the `SQLServerExecutor` route, but replaces executor execution with a fail-if-called hook. This proves the refusal happens before DB execution or memory fallback.

Cascade regression command:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py -q -rs
```

Result:

```text
32 passed in 1.38s
```

Full regression command:

```powershell
pytest -q
```

Result:

```text
3940 passed in 11.51s
```

## Signoff

Status: accepted-refusal for Python Pivot v1.10 P2.

Functional impact:

- LLM-generated SQL Server cascade requests receive a stable explicit refusal.
- SQLite/MySQL8/PostgreSQL C2 cascade remains the supported runtime path.
- SQL Server oracle parity remains a future enhancement, not a v1.10 supported feature.
