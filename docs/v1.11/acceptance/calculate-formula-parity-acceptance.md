# CALCULATE / Formula Parity Acceptance

## 文档作用

- doc_type: acceptance
- status: accepted-with-profile-note
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 签收 v1.11 P1 受限 CALCULATE / formula parity，确认公开提示词中的 CALCULATE 子集具备真实 SQL oracle 证据，非支持语义 fail-closed。

## Scope

本次签收只覆盖公开提示词已经暴露的受限形态：

```text
CALCULATE(SUM(metric), REMOVE(groupByDim...))
```

典型用途：

- 全局占比：移除当前唯一分组维度。
- 组内占比：在多维 `groupBy` 中移除子级维度，保留其余维度作为窗口分区。

不扩大 DSL，不支持任意 MDX 坐标漫游，不支持嵌套 CALCULATE。

## Accepted Behavior

| Behavior | Decision | Evidence |
|---|---|---|
| `CALCULATE(SUM(metric), REMOVE(groupByDim))` | accepted | compiler catalog + service validate + three-DB oracle |
| `NULLIF(CALCULATE(...), 0)` denominator guard | accepted|required | catalog refusal covers missing NULLIF |
| remove one dim and keep remaining `groupBy` as window partition | accepted | real DB partition-share oracle |
| scalar wrapper such as `ROUND(...)` | accepted | catalog |
| remove non-grouped field | fail-closed | catalog |
| remove system-sliced field | fail-closed | catalog |
| nested CALCULATE | fail-closed | catalog |
| timeWindow post calculatedFields with CALCULATE | fail-closed | catalog |
| conservative `mysql` dialect / MySQL 5.7-style profile | fail-closed | service test |

## Oracle Evidence

Commands run:

```powershell
pytest tests/test_dataset_model/test_calculate_mvp_service.py tests/test_dataset_model/test_calculate_mvp_parity_catalog.py tests/test_mcp/test_query_model_calculate_prompt.py tests/integration/test_calculate_mvp_real_db_matrix.py -q -rs
```

Result:

```text
19 passed in 0.62s
```

The integration matrix executed SQLite, MySQL 8, and PostgreSQL with 0 skipped tests. The query_model result rows were compared to handwritten SQL using grouped aggregate windows:

```sql
SUM(f.sales_amount) / NULLIF(SUM(SUM(f.sales_amount)) OVER (...), 0)
```

## MySQL Profile Note

Python keeps the historical `MySqlDialect` conservative because the same executor class may point to MySQL 5.7-style deployments. MySQL 8 parity is enabled through the explicit `MySql8Dialect` capability profile, which sets `supports_grouped_aggregate_window = true`.

This is an accepted profile-selection note, not a public DSL change.

## Decision

P1 CALCULATE / Formula parity is accepted with the MySQL profile note above.

Remaining v1.11 work moves to P2 timeWindow current evidence refresh.
