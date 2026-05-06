# P1-list_models discovery catalog contract

## 文档作用

- doc_type: workitem / progress
- intended_for: execution-agent / reviewer / bridge-consumer
- purpose: 记录 2026-05-06 口径调整后，`dataset.list_models` 作为唯一 LLM 首轮模型发现入口的 Python 侧契约。
- version: v1.6
- priority: P1
- status: ready-for-review
- owning repo: foggy-data-mcp-bridge-python
- related root doc: `docs/v1.6/P0-engine-native多模型metadata工具-需求.md`
- related Java doc: `foggy-data-mcp-bridge/docs/8.3.0.beta/P2-list_models模型发现入口与get_metadata隐藏-需求.md`

## Contract Decision

不新增独立 `dataset.describe_models`。

`dataset.list_models` 是 LLM 首次获取当前系统可用模型的唯一入口。由于外部 MCP client 无法依赖 Odoo Bridge Pro 的内置 system prompt，LLM 必须能直接通过该工具发现可查询模型。

## Public MCP Schema

`dataset.list_models` 的 LLM 可见 schema 暂时不加入参数：

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

LLM 可见 schema 不暴露 `format`、`modelNames`、`models`、`visibleFields`、`deniedColumns`、`fieldLimit`、`llmHints` 或 `detail`。

Host / bridge 作为程序化调用方访问 engine catalog 能力时，不通过 MCP tool arguments，而使用标准 Controller POST 入口：

```text
POST /semantic/v3/list-models
```

该 POST body 可以传固定 `format=markdown`、`fieldLimit=20`、principal-specific `modelNames` / `visibleFields` / `deniedColumns`。这些参数不进入 LLM-facing MCP schema，也不要求 LLM 拼装。

## Output Shape

输出保持旧调用方兼容：

```json
{
  "models": ["OdooAccountMoveQueryModel"],
  "count": 1,
  "recommendedNext": "dataset.describe_model_internal",
  "items": [
    {
      "model": "OdooAccountMoveQueryModel",
      "caption": "Invoice & Billing Analysis",
      "description": "Invoice and bill headers...",
      "namespace": "odoo",
      "physicalTables": ["account_move"],
      "recommendedNext": "dataset.describe_model_internal",
      "fieldPreview": ["id", "name", "moveType", "invoiceDate"],
      "fieldCount": 42
    }
  ]
}
```

`items` 是模型级 discovery catalog，不是字段详情接口。字段类型、timeRole、公式、维度、度量等仍由 `dataset.describe_model_internal` 返回。

## Implementation Notes

- Python MCP `dataset.list_models` schema 不暴露参数；MCP route 忽略调用 arguments，只作为 LLM 首轮模型发现入口。
- `POST /semantic/v3/list-models` 是 Odoo Bridge Pro 等 host 程序化调用方的参数化入口，用于固定格式、字段预览数量和权限裁剪输入。
- `SemanticQueryService.get_model_catalog(...)` 作为内部 DTO builder 保留，承接 `model_names`、`visible_fields`、`denied_columns`、`llm_hints`、`field_limit`。
- Markdown 如需提供，应从同一 DTO 渲染；调用方不应解析 Markdown 来做权限过滤。
- Host-specific routing hints 暂不进入 engine public schema；Odoo Bridge Pro 可以继续在桥接层维护业务提示。

## Host API

Request:

```json
{
  "format": "markdown",
  "fieldLimit": 20,
  "modelNames": ["OdooAccountMoveQueryModel"],
  "visibleFields": ["id", "name", "invoiceDate"],
  "deniedColumns": [{"table": "account_move", "columns": ["private_note"]}]
}
```

Response:

```json
{
  "format": "markdown",
  "content": "# Model Catalog\n...",
  "data": {
    "models": ["OdooAccountMoveQueryModel"],
    "count": 1,
    "recommendedNext": "dataset.describe_model_internal",
    "items": []
  }
}
```

## Acceptance Criteria

- [x] `dataset.list_models` schema 是空对象。
- [x] Existing callers reading `models: string[]` continue to work.
- [x] Rich `items` remain lightweight model-level discovery data.
- [x] MCP public route does not expose or require parameters.
- [x] `dataset.describe_model_internal` remains the next-step field detail tool.

## Progress Tracking

### Development Progress

| Item | Status | Evidence |
|------|--------|----------|
| Python service DTO builder | completed | `src/foggy/dataset_model/semantic/service.py` |
| Python MCP public route | adjusted | `src/foggy/mcp/routers/mcp_rpc.py` keeps no-parameter schema and ignores arguments |
| Python host Controller route | completed | `src/foggy/mcp/routers/semantic_v3.py` exposes `POST /semantic/v3/list-models` |
| Python legacy tool compatibility | adjusted | `src/foggy/mcp/tools/metadata_tool.py` keeps no-param behavior |
| Java parity implementation | adjusted | `foggy-dataset-mcp/src/main/java/com/foggyframework/dataset/mcp/tools/ListModelsTool.java` |
| Odoo Bridge Pro refactor | deferred | Odoo remains consumer/reference in this task |

### Testing Progress

| Command | Status | Result |
|---------|--------|--------|
| `python -m pytest tests\test_mcp\test_list_models_tool.py tests\test_mcp\test_mcp_rpc_router.py tests\test_mcp\test_semantic_v3_list_models_catalog.py -q` | passed | 34 passed |
| `python -m pytest tests\test_mcp\test_list_models_tool.py tests\test_mcp\test_mcp_rpc_router.py tests\test_mcp\test_semantic_v3_list_models_catalog.py tests\test_mcp\test_compose_script_tool.py tests\test_mcp\test_compose_script_tool_binding.py -q` | passed | 65 passed |
| `python -m pytest tests\test_mcp -q` | passed | 205 passed |
| `mvn -pl foggy-dataset-mcp -Dtest=ListModelsToolTest test` | passed | 13 passed |
| `mvn -pl foggy-dataset-mcp -am -Dtest=ListModelsToolTest '-Dsurefire.failIfNoSpecifiedTests=false' test` | passed | 13 passed; dependent modules recompiled |

### Execution Check-in — 2026-05-06

Status: `ready-for-review`

Completed:

- `dataset.list_models` MCP public schema remains empty and ignores LLM-supplied arguments.
- `POST /semantic/v3/list-models` provides the host-facing parameterized catalog endpoint.
- `SemanticQueryService.get_model_catalog()` builds the canonical JSON DTO, and markdown rendering is derived from that DTO.
- `compose_script` output no longer fabricates `semantic.shouldAnswerDirectly`; SQL-backed query results now expose `executionEvidence`, while orchestration/literal results remain valid without SQL evidence.

Verification:

- `python -m pytest tests\test_mcp\test_list_models_tool.py tests\test_mcp\test_mcp_rpc_router.py tests\test_mcp\test_semantic_v3_list_models_catalog.py tests\test_mcp\test_compose_script_tool.py tests\test_mcp\test_compose_script_tool_binding.py -q` -> `65 passed`.
- `python -m pytest tests\test_mcp -q` -> `205 passed`.
