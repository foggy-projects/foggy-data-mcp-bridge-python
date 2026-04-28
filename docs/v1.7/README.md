# v1.7 — v1.3 引擎收紧裸 dimension 引用

## 文档作用

- doc_type: workitem-group
- intended_for: execution-agent / reviewer
- purpose: 跟踪 backlog `B-03` 抬升为正式需求后的实施进度，跨双端（Java `8.4.0.beta`）同步交付

## 进度总览

| 功能 | 状态 | 备注 |
|------|------|------|
| `P0-v13引擎收紧裸dimension引用` | `in-design` | 需求文档已落盘 · M0 立项 · M1 跨端审计待启动 |

## 功能清单

| 文件 | 用途 |
|------|------|
| `P0-v13引擎收紧裸dimension引用-需求.md` | 改造路径 / 当前行为审计 / 验收标准 / 测试计划 |
| `P0-v13引擎收紧裸dimension引用-progress.md` | M0-M12 里程碑 + Self-Check + 决策记录 |

## 关联文档

- backlog 起源：`foggy-data-mcp-bridge-python/docs/backlog/B-03-v13-engine-bare-dimension-tightening.md`
- Java 端镜像：`foggy-data-mcp-bridge/docs/8.4.0.beta/P0-v13引擎收紧裸dimension引用-{需求,progress}.md`
  - 物理路径：`D:/foggy-projects/foggy-data-mcp/foggy-data-mcp-bridge-wt-dev-compose/docs/8.4.0.beta/`
- 上游触发：G5 PR-P2 调试期复盘（commit `cf2ba9b` → `352a8bb`）
- 受影响 spec：
  - `foggy-data-mcp-bridge/docs/8.3.0.beta/P0-SemanticDSL-列项对象语法-后置消歧设计.md` §4.2 用户级开放门
  - `foggy-data-mcp-bridge/docs/8.3.0.beta/G10-flag-flip-rollout-playbook.md` C1-C4 决策门

## 当前优先级判断

P0 — 影响 LLM 公开契约一致性 + 测试基线稳定性 + G5 F5 用户级开放门成立条件之一。

## 改造路径

**Path A · 严格化**（用户决策 · 2026-04-28）：fail-loud 拒绝裸 dimension + 拒绝 dimension AS alias + 修复 dimension$attr AS alias 用户 alias 透传 bug。

详见需求文档"目标"小节。
