# v1.8 — Pivot V9 Python Parity

## 文档作用

- doc_type: workitem-group
- intended_for: root-controller / execution-agent / reviewer
- purpose: 跟踪 Java Pivot V9 release-ready 能力向 Python 引擎镜像迁移的审计、规划、执行与验收。

## 进度总览

| 功能 | 状态 | 备注 |
|---|---|---|
| `P0-Pivot-V9-Python-Parity` | `s3-grid-shaping-and-axis-operations-complete` | 已完成 S3 Grid Shaping：实现 `outputFormat=grid`、`rowHeaders`/`columnHeaders`/`cells`、`having`、`orderBy`/`limit` 以及 `crossjoin`。已通过 SQLite/MySQL8/Postgres oracle parity；其余高级特性保持 fail-closed。 |

## 功能清单

| 文件 | 用途 |
|---|---|
| `P0-Pivot-V9-Python-Parity-Gap-Report.md` | Python 与 Java Pivot V9 的能力差距、S1 完成证据、后续执行分期和非目标 |

## 关联文档

- Java 设计与签收基线：`D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.0.0.beta/`
- Java release readiness：`D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.0.0.beta/acceptance/s13_release_readiness.md`
- Java Python parity 初始规划：`D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/9.0.0.beta/acceptance/s10_python_parity_plan.md`
