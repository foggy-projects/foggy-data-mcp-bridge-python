# v1.6 — 跨模型列权限泄漏修复（F-3）

## 文档作用

- doc_type: workitem-group
- intended_for: execution-agent / reviewer
- purpose: 跟踪 v1.4 REQ-FORMULA-EXTEND 签收遗留 F-3 的正式修复，解锁 8.2.0.beta Compose Query 与 Odoo Pro v1.6 REQ-001 两条下游线

## 进度总览

| 功能 | 状态 | 备注 |
|------|------|------|
| `P0-BUG-F3` `_resolve_effective_visible` 跨模型 denied 泄漏修复 | `in-progress` | **Python 侧已修（2430 passed / M2-M6 完成）** · **Java 侧同步修复待启动（M7）** · Odoo Pro 撤 xfail + vendored sync 待联调 |

## 功能清单

| 文件 | 用途 |
|------|------|
| `P0-BUG-F3-resolve-effective-visible-cross-model-denied-leak-需求.md` | 正式修复需求、根因分析、方案、测试计划、验收 |
| `P0-BUG-F3-progress.md` | 执行进度骨架（M0-M12） |

## 关联文档

- v1.4 签收 Follow-up 清单（F-3 定义）：Odoo Pro `docs/v1.4/acceptance/REQ-FORMULA-EXTEND-non-aggregation-functions-acceptance.md`
- 上游 BUG 工单：`foggy-odoo-bridge-pro/docs/prompts/v1.4/workitems/BUG-v14-metadata-v3-denied-columns-cross-model-leak.md`
- 下游 blocker：
  - `foggy-data-mcp-bridge/docs/8.2.0.beta/P0-ComposeQuery-*-需求.md §前置依赖`
  - `foggy-odoo-bridge-pro/docs/prompts/v1.6/P0-01-compose-query-embedded-authority-resolver-需求.md §前置依赖`

## 当前优先级判断

- `P0-BUG-F3` 是两条下游工作流的 blocking 前置
- 不是普通 follow-up，必须按正式修复需求推进，走完签收流程
- Java 侧是否同步修复由 M6 grep 判定，条件性执行
- 修复完成后必须触发 Odoo Pro vendored sync + root CLAUDE.md 状态回写
