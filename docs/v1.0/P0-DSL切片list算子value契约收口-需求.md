# P0-DSL 切片 list 算子 `value` 契约收口-需求

## 基本信息
- 目标版本：`v1.0`
- 需求等级：`P0`
- 状态：`已完成`
- 完成日期：2026-04-05
- 责任项目：`foggy-data-mcp-bridge-python`

## 完成记录

### 开发进度：已完成

改动文件：`src/foggy/dataset_model/definitions/query_request.py`

| 改动 | 说明 |
|------|------|
| `CondRequestDef.values` 字段添加 `exclude=True` | 序列化时不再输出 `values`，公开 JSON 只有 `value` |
| 新增 `model_post_init` | 构造时将 `values` 归一到 `value`（历史兼容） |
| `to_sql()` 更新 | 优先使用 `value`（已归一），`values` 作为 fallback |
| 文档注释 | 明确标注 `values` 为 deprecated 输入兼容 |

### 测试进度：已完成

- `pytest tests/`: 1388 passed, 76 skipped, 0 failed

### 体验进度：N/A

## 背景
2026-04-02 在 Odoo bridge 本地快测中，`tests/test_permission_bridge.py` 大量失败。根因不是权限桥接逻辑本身出错，而是测试仍按历史字段 `values` 断言，而当前实现已统一对 `in` / `not in` 输出：

- 标准字段：`value`
- 非标准旧字段：`values`

进一步核对后，当前真实消费契约已收敛为：

- Java 侧 DSL 契约：只认 `value`
- Python 侧消费路径：为兼容旧输入可读 `value` / `values`
- Python 侧对外输出：应遵守 Java 主契约，只使用 `value`

因此这个问题的本质不是“要不要同时支持两套字段”，而是“Python 不得继续向外漂移出 `values` 契约”。

## 当前共识
- `in` / `not in` 的公开 DSL 输出字段统一为 `value`
- `values` 只允许作为历史兼容输入的读路径容错，不得继续作为文档、测试、示例、controller 注入结果或 gateway 输出的标准字段
- 新增 contract、E2E、示例时均以 `value` 为准

## 目标
- 锁定 Python 与 Java 的 slice 契约一致性
- 防止后续因为历史测试、示例或局部修补再次把 `values` 带回公开输出

## 任务拆分

### 1. Python DSL 产出链路
- 复核所有 list 算子输出点，确保公开输出只写 `value`
- controller 注入、permission bridge、gateway 输出、contract fixture 一律遵守同一字段

### 2. Python 兼容策略
- 如保留 `values` 输入兼容，只允许存在于解析/归一化读路径
- 兼容分支需在注释中明确写明“历史兼容，不是标准契约”

### 3. Python 测试与文档
- contract test 明确断言 `in` / `not in` 使用 `value`
- 清理或更新仍以 `values` 为准的单测、示例、文档
- 新增回归测试，防止公开输出字段回漂

## 验收标准
- Python 公开返回的 slice JSON 中，`in` / `not in` 条件只出现 `value`
- 不再新增依赖 `values` 的测试断言
- Java/Python/Odoo 三侧对 DSL slice 的示例文档一致

## 非目标
- 本条不要求删除所有历史兼容读取逻辑
- 本条不改变 list 算子的语义，只收口字段命名契约
