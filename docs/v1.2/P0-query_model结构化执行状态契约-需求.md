# P0 — query_model 结构化执行状态契约（Python）— 需求

## 文档作用

- doc_type: `requirement`
- intended_for: `sub-agent`
- purpose: 为 Python 引擎定义 `query_model` 成功 / 失败结构化响应契约，并支撑 v1.2 导出候选过滤 BUG 修复

## 基本信息

- 目标版本：`v1.2`
- 需求等级：`P0`
- 状态：`draft`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游文档：`docs/v1.2/P0-query_model结构化执行状态与导出候选过滤-需求.md`（workspace root）

## 当前问题

Python 侧已经有内部错误概念，但 `query_model` 的 MCP 对外结果里缺少一个足够简单、稳定的状态字段。

当前缺口是：

- `mcp_rpc.py` 对 `query_model` 的 MCP 包装仍以 `result.content[].text` 为主
- 业务失败时还可能直接走顶层 JSON-RPC `error`

这会让 Odoo 导出链路无法稳定消费成功 / 失败状态，只能依赖文本或路由行为推断。

## 需求范围

### 1. MCP 返回增加 result.status

`mcp_rpc.py` 中 `tools/call -> dataset.query_model` 需要在 `result` 下增加：

- `status: success | failed`

返回形态示例：

```json
{
  "result": {
    "status": "failed",
    "content": [
      {
        "type": "text",
        "text": "查询被拒绝：column \"totalamount\" does not exist"
      }
    ]
  }
}
```

### 2. 失败响应构造

`mcp_rpc.py` 中 `tools/call -> dataset.query_model` 需要：

- 失败时返回 `result.status=failed`
- 成功时返回 `result.status=success`
- 继续返回 `result.content[].text`
- 对业务级查询失败不再只依赖顶层 JSON-RPC `error`

顶层 JSON-RPC `error` 仅保留给：

- 缺少 `model`
- 缺少 `payload`
- 未知工具
- 协议 / 运行时异常

## 向后兼容约束

- `result.content[].text` 继续保留
- `status` 只新增在 MCP `result` 下，不要求本轮扩散到内部所有响应模型
- 现有依赖 `response.error` 的内部调用点可以继续工作，但不能作为唯一失败表达方式

## Code Inventory

- path: `src/foggy/mcp_spi/accessor.py`
  - role: 查询响应透传
  - expected_change: `read-only-analysis`
  - notes: 确认失败场景在路由层可被稳定映射为 `status=failed`

- path: `src/foggy/dataset_model/semantic/service.py`
  - role: 失败响应来源
  - expected_change: `read-only-analysis`
  - notes: 确认当前错误是在何处生成，避免重复包装

- path: `src/foggy/mcp/routers/mcp_rpc.py`
  - role: MCP `tools/call` 包装
  - expected_change: `update`
  - notes: 在 `result` 下增加 `status`，并调整 JSON-RPC 错误边界

## 验收标准

1. 对非法 alias 排序场景，Python 返回：
   - `result.status=failed`
   - `result.content[].text` 中保留当前错误文案
2. 对正常查询场景，返回：
   - `result.status=success`
3. 业务级查询失败不再只能通过顶层 JSON-RPC `error` 体现
4. 现有成功查询的字段结构不回归

## 非目标

- 不在本条中实现 Odoo 导出弹窗逻辑
- 不在本条中定义 v1.3 的 checkbox 多选和预览
- 不在本条中新增新的错误码体系
