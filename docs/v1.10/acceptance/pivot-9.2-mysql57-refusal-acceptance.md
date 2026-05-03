# Pivot 9.2 MySQL 5.7 Refusal Acceptance

## 文档作用

- doc_type: feature-acceptance
- status: accepted-refusal
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 记录 Python Pivot v1.10 P3 MySQL 5.7 cascade / large-domain transport 的拒绝证据和签收边界。

## Scope

P3 不实现 MySQL 5.7 C2 cascade staged SQL，也不实现 MySQL 5.7 large-domain transport renderer。P3 只签收以下行为：

- 显式 `mysql5.7` 方言不能冒充 MySQL8。
- C2 cascade 在 `mysql5.7` 下返回稳定 `PIVOT_CASCADE_SQL_REQUIRED`。
- large-domain `DomainTransportPlan` 在 `mysql5.7` 下返回稳定 `PIVOT_DOMAIN_TRANSPORT_REFUSED`。
- 两条路径都必须在 executor SQL 执行前 fail-closed。

不改变 public Pivot DSL，不新增 schema 字段，不声明 MySQL 5.7 oracle parity。

## Decision

Status: accepted-refusal.

MySQL 5.7 继续不属于 Python Pivot C2 cascade 支持范围：

- MySQL 5.7 缺少窗口函数能力，不能执行 C2 staged ranking。
- 当前 MySQL8 renderer 使用 CTE / window 语义，不能降级套用到 5.7。
- Python 项目当前没有 live MySQL 5.7 profile；因此只能签收显式方言 refusal，不签收 oracle parity。

## Evidence

Targeted P3 command:

```powershell
pytest tests/integration/test_pivot_v9_cascade_mysql57_matrix.py -q -rs
```

Result:

```text
2 passed in 0.25s
```

The tests use an explicit `MySql57Dialect` and a fail-if-called executor. This proves `mysql5.7` requests are refused before SQL execution.

Refusal/domain regression command:

```powershell
pytest tests/integration/test_pivot_v9_cascade_mysql57_matrix.py tests/integration/test_pivot_v9_cascade_sqlserver_matrix.py tests/test_dataset_model/test_pivot_v9_domain_transport.py -q -rs
```

Result:

```text
34 passed in 0.28s
```

Cascade regression command:

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```

Result:

```text
30 passed in 3.26s
```

Full regression command:

```powershell
pytest -q
```

Result:

```text
3942 passed in 16.18s
```

## Signoff

Status: accepted-refusal for Python Pivot v1.10 P3.

Functional impact:

- MySQL8 remains the supported MySQL cascade profile.
- MySQL 5.7 remains fail-closed for cascade and large-domain transport.
- Future MySQL 5.7 support requires a separate live profile and oracle evidence.
