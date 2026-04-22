# 8.2.0.beta Compose Query — Python 侧本地副本

## 这里是什么

本目录是从 Java 仓 (`foggy-data-mcp-bridge`) 的 `dev-compose` 分支 worktree 复制过来的**快照**，便于 Python 工程师在本仓内本地开工 M6 时直接读，无需切换仓库或打开远端。

快照时间：**2026-04-22**（M5 Java 落地之后，M6 Python 开工之前）。

## 权威来源

所有 8.2.0.beta Compose Query 规范文档的**权威版本**都在 Java 仓：

```
foggy-data-mcp-bridge (origin/dev-compose)
  └── docs/8.2.0.beta/
      ├── P0-ComposeQuery-QueryPlan派生查询与关系复用规范-需求.md       ← spec
      ├── P0-ComposeQuery-QueryPlan派生查询与关系复用规范-实现规划.md   ← implementation plan
      ├── P0-ComposeQuery-QueryPlan派生查询与关系复用规范-代码清单.md   ← code inventory
      ├── P0-ComposeQuery-QueryPlan派生查询与关系复用规范-progress.md   ← milestone / changelog / decisions
      ├── P0-ComposeQuery-固定Schema下业务分析能力对比评估.md           ← 只读参考
      ├── P0-ComposeQuery-沙箱白名单错误码与防护用例清单.md             ← M9 scope
      ├── M1-AuthorityResolver-SPI签名冻结-需求.md
      ├── M2-QueryPlan-Java-execution-prompt.md
      ├── M3-Dialect-and-SandboxErrors-Java-execution-prompt.md
      ├── M4-SchemaDerivation-Java-execution-prompt.md
      ├── M5-AuthorityBinding-Java-execution-prompt.md
      ├── M6-SQLCompilation-Python-execution-prompt.md   ← this repo 首发
      └── M9-三层沙箱防护测试脚手架.md
```

如果权威版与本副本冲突，**以权威版为准**；本副本会在 M6 Python 工作推进过程中尽量保持同步，但以下 workflow 才是保证一致性的正确做法：

- **读**：打开 Java 仓 origin/dev-compose 的这几份文档；本副本仅作为"离线阅读方便"的兜底
- **写/回填**（更新 progress.md 的 M6 行、追加 changelog、改决策记录等）：先回写到 Java 仓 worktree，再由 Python 工程师把更新的 `progress.md` 重新 copy 过来（或直接在 PR 描述中引用 Java 仓 commit hash）。**不要**在这份本地副本上单独改动

## 为什么 Python 仓也放一份

- Python 侧 M1–M5 都是直接读 Java 仓里的 spec 开工，没有 per-milestone 的 Python-specific execution prompt。那时量级小，能 work。
- M6 是 Compose Query 里最大的里程碑（首次跨 BaseModelPlan 组合 SQL，涉及 v1.3 挂点注入、4 方言 CTE vs 子查询回退、plan-hash 子树去重），需要一份聚焦的开工提示词。
- M6 提示词 `M6-SQLCompilation-Python-execution-prompt.md` 是 Python 工程师的直接工作手册；spec / 实现规划 / 代码清单是它引用的前置读物；progress.md 决策记录有 2026-04-22 两条锁定 M6 范围的 decisions（v1.3 `deniedColumns` 复用 / 节奏 Python 先落）必读。
- 为了这次开工一次把 5 份文档全搬过来，Python 工程师看完提示词就能找到所有引用资料。

## 当前里程碑状态（快照时刻 · 以 progress.md 为准）

| # | 阶段 | Python | Java |
|---|------|--------|------|
| M1 | SPI 签名冻结 | ✅ ready-for-review | ✅ ready-for-review |
| M2 | QueryPlan 对象模型 | ✅ ready-for-review | ✅ ready-for-review |
| M3 | Dialect + Sandbox 错误契约 | ✅ ready-for-review | ✅ ready-for-review |
| M4 | Schema 推导与别名 / 冲突校验 | ✅ ready-for-review | ✅ ready-for-review |
| M5 | Authority 绑定管线 | ✅ ready-for-review | ✅ ready-for-review |
| **M6** | **SQL 编译器** | **⏳ ready-to-execute（本目录 M6 提示词）** | 待 Python 落地后镜像 |
| M7 | MCP script 工具入口 | not-started | not-started |
| M8 | Odoo Pro 嵌入验收 | partial | — |
| M9 | 三层沙箱防护测试集 | not-started | not-started |
| M10 | 集成测试 + 签收 | not-started | not-started |

## 开工顺序建议

Python 工程师按这个顺序读：

1. 本 README（你现在在这）
2. `M6-SQLCompilation-Python-execution-prompt.md` ← 工作手册
3. 提示词 §必读前置 指到的章节：
   - `需求.md` §SQL 编译边界 / §错误模型规划 / §典型示例 1~3
   - `实现规划.md` §SQL 编译边界 (§1~§4) / §交付顺序建议 第 6 条
   - `progress.md` §决策记录 2026-04-22 两条
4. 开始实现
