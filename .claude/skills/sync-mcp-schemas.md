# sync-mcp-schemas

同步 Java 和 Python 两端的 MCP 工具定义（描述、参数 Schema）。

## 触发条件
当用户提到 "同步MCP"、"sync schemas"、"同步工具定义"、"/sync-mcp" 时使用。

## 工作流程

### 1. 检查差异
```bash
cd D:/foggy-projects/foggy-dataset-py/foggy-python
python scripts/sync_mcp_schemas.py --diff
```

### 2. 预览同步（不实际复制）
```bash
python scripts/sync_mcp_schemas.py --dry-run
```

### 3. 执行同步
```bash
python scripts/sync_mcp_schemas.py
```

### 4. 包含 Addon 同步
```bash
python scripts/sync_mcp_schemas.py --include-addons
```

### 5. 指定 Java 项目路径
```bash
python scripts/sync_mcp_schemas.py --java-root D:/foggy-projects/foggy-data-mcp-bridge
```

### 6. 同步后验证
```bash
cd D:/foggy-projects/foggy-dataset-py/foggy-python
python -m pytest tests/test_mcp/ --tb=short -q
```

## 文件映射

| Java 源文件 | Python 目标文件 |
|---|---|
| `foggy-dataset-mcp/src/main/resources/schemas/*.json` | `src/foggy/mcp/schemas/*.json` |
| `foggy-dataset-mcp/src/main/resources/schemas/descriptions/*.md` | `src/foggy/mcp/schemas/descriptions/*.md` |

## 架构说明

```
Java (Source of Truth)                    Python (Consumer)
─────────────────────                    ─────────────────
schemas/                                 src/foggy/mcp/schemas/
├── get_metadata_schema.json     ──→     ├── get_metadata_schema.json
├── query_model_v3_schema.json   ──→     ├── query_model_v3_schema.json
├── ...                                  ├── ...
├── descriptions/                        ├── descriptions/
│   ├── get_metadata.md          ──→     │   ├── get_metadata.md
│   ├── query_model_v3.md        ──→     │   ├── query_model_v3.md
│   └── ...                              │   └── ...
                                         └── tool_config_loader.py  ← 运行时加载器
```

**工作流**：Java 侧修改工具描述/schema → 运行 sync 脚本 → Python 侧自动生效（无需改代码）

## 注意事项
- Java 项目是 source of truth，不要在 Python 侧直接修改 schema 文件
- 同步后如果新增了工具，需要在 `tool_config_loader.py` 的 `BUILTIN_TOOLS` 中注册
- 同步后如果新增了工具，需要在 `mcp_rpc.py` 的 `handle_request` 中添加处理逻辑
