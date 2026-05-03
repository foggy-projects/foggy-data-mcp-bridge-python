# Pivot 9.2 Production Telemetry and Log Query Examples

## 文档作用

- doc_type: operations-guide
- status: accepted-docs
- intended_for: ops / support / python-engine-agent / signoff-owner
- purpose: 记录 Python Pivot v1.10 生产排障可用的日志 marker、错误分类和安全查询示例。

## Scope

本文件只整理当前运行时已经存在或可稳定依赖的观测信号，不新增 runtime telemetry，不改变 public Pivot DSL。

目标：

- 区分 DomainTransport 成功/拒绝。
- 区分 cascade refusal、unsupported dialect、执行失败。
- 给后续 outer Pivot cache feasibility 提供最小生产排障口径。

非目标：

- 不记录物理列名、SQL 参数值或用户输入明文。
- 不要求应用日志输出完整 SQL。
- 不声明 dashboard 已落地。

## Current Signals

| Signal | Source | Meaning | Sensitive Data Risk |
|---|---|---|---|
| `PIVOT_DOMAIN_TRANSPORT: dialect=..., strategy=..., tuple_count=..., column_count=...` | `domain_transport.py` info log | large-domain transport renderer was selected | low; no values logged |
| `PIVOT_DOMAIN_TRANSPORT_REFUSED` | response error / exception text | domain transport cannot be rendered safely | low if only prefix/classification is indexed |
| `PIVOT_CASCADE_SQL_REQUIRED` | response error | cascade requires staged SQL but current dialect/path is unsupported | low |
| `PIVOT_CASCADE_SCOPE_UNSUPPORTED` | response error | unsupported cascade shape such as three-level/columnSubtotal | low |
| `PIVOT_CASCADE_NON_ADDITIVE_REJECTED` | response error | non-additive or derived metric attempted in cascade | low |
| `PIVOT_CASCADE_TREE_REJECTED` | response error | tree+cascade is still deferred | low |
| `Cascade execution failed` | response error | staged SQL was emitted but DB execution failed | medium; current error may include DB engine message |

## Safe Log Query Examples

These examples intentionally match stable prefixes and avoid selecting raw SQL or parameter fields.

Plain text / grep:

```bash
grep -E "PIVOT_DOMAIN_TRANSPORT:|PIVOT_DOMAIN_TRANSPORT_REFUSED|PIVOT_CASCADE_" app.log
```

Loki / LogQL:

```logql
{app="foggy-python"} |= "PIVOT_DOMAIN_TRANSPORT:"
```

```logql
{app="foggy-python"} |~ "PIVOT_DOMAIN_TRANSPORT_REFUSED|PIVOT_CASCADE_[A-Z_]+"
```

Elastic / KQL:

```kql
message : "PIVOT_DOMAIN_TRANSPORT:" or message : "PIVOT_DOMAIN_TRANSPORT_REFUSED" or message : "PIVOT_CASCADE_*"
```

SQL-style log table:

```sql
SELECT
  date_trunc('hour', ts) AS hour_bucket,
  CASE
    WHEN message LIKE '%PIVOT_DOMAIN_TRANSPORT:%' THEN 'domain_transport_used'
    WHEN message LIKE '%PIVOT_DOMAIN_TRANSPORT_REFUSED%' THEN 'domain_transport_refused'
    WHEN message LIKE '%PIVOT_CASCADE_SQL_REQUIRED%' THEN 'cascade_sql_required'
    WHEN message LIKE '%PIVOT_CASCADE_SCOPE_UNSUPPORTED%' THEN 'cascade_scope_unsupported'
    WHEN message LIKE '%PIVOT_CASCADE_NON_ADDITIVE_REJECTED%' THEN 'cascade_non_additive_rejected'
    WHEN message LIKE '%PIVOT_CASCADE_TREE_REJECTED%' THEN 'cascade_tree_rejected'
    ELSE 'other'
  END AS pivot_event,
  COUNT(*) AS events
FROM app_logs
WHERE message LIKE '%PIVOT_DOMAIN_TRANSPORT%'
   OR message LIKE '%PIVOT_CASCADE_%'
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
```

## Interpretation Guide

| Observation | Likely Cause | Action |
|---|---|---|
| Frequent `PIVOT_DOMAIN_TRANSPORT:` with high `tuple_count` | large surviving domains are common | evaluate P5 outer cache only after confirming latency impact |
| `PIVOT_DOMAIN_TRANSPORT_REFUSED` on `mysql5.7` | unsupported 5.7 renderer | keep fail-closed; route to MySQL8/Postgres/SQLite if cascade is required |
| `PIVOT_CASCADE_SQL_REQUIRED` on `sqlserver` | SQL Server cascade is accepted-refusal in v1.10 | do not retry with memory fallback; collect SQL Server oracle requirement |
| `PIVOT_CASCADE_SCOPE_UNSUPPORTED` | unsupported shape such as three-level cascade or column subtotal | simplify request to two-level rows cascade or use compose workflow |
| `PIVOT_CASCADE_TREE_REJECTED` | tree+cascade requested | wait for P4 semantic decision; current runtime must refuse |
| `Cascade execution failed` | DB rejected staged SQL or fixture/schema mismatch | inspect sanitized SQL only in trusted dev environment |

## Privacy and Safety Rules

- Log classification prefix, dialect, strategy, tuple count, and column count only.
- Do not log domain tuple values.
- Do not log user-provided filter values.
- Do not index raw SQL in shared dashboards unless the deployment has a sanitizer review.
- Treat DB engine messages as medium risk because they may include identifiers.

## Known Gaps

- Cascade success path has no structured `PIVOT_CASCADE_EXECUTED` marker yet.
- There is no production latency histogram or dashboard in this repo.
- Oracle profile skipped states are currently test-runner output, not runtime telemetry.
- P5 outer cache remains deferred until production latency evidence exists.
