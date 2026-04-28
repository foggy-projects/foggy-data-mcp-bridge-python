# P2-S7a Stable Relation Python Mirror Progress

## 基本信息

- version: 1.5.0 (S7a)
- status: mirror-complete
- java_contract_ref: `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7a-stable-relation-contract-progress.md`
- java_contract_version: S7a-1
- java_snapshot: consumed `target/parity/_stable_relation_schema_snapshot.json`

## Python Mirror 概览

Python S7a mirror 完全对齐 Java S7a POC 的模型和约束，同时遵循 Python 项目的 frozen dataclass / frozenset / type annotation 约定。

## 新增模块

### `relation/` 包 (3 files)

| 文件 | 说明 |
|---|---|
| `relation/__init__.py` | Re-exports |
| `relation/constants.py` | SemanticKind, ReferencePolicy, RelationWrapStrategy, RelationPermissionState |
| `relation/models.py` | CteItem, RelationSql, RelationCapabilities, CompiledRelation |

## ColumnSpec 扩展

新增 4 个 Optional metadata 字段（excluded from `__eq__`/`__hash__`）：
- `semantic_kind: Optional[str]`
- `value_meaning: Optional[str]`
- `lineage: Optional[FrozenSet[str]]`
- `reference_policy: Optional[FrozenSet[str]]`

## Error Codes 扩展

### schema/error_codes.py (+2)
- `RELATION_OUTPUT_SCHEMA_UNAVAILABLE`
- `RELATION_COLUMN_REFERENCE_UNSUPPORTED`

### compilation/error_codes.py (+3)
- `RELATION_WRAP_UNSUPPORTED`
- `RELATION_CTE_HOIST_UNSUPPORTED`
- `RELATION_DATASOURCE_MISMATCH`

## 测试证据

### 新增测试
| 文件 | 说明 |
|---|---|
| `tests/compose/schema/test_column_spec_metadata.py` | ColumnSpec metadata defaults, equality, hash |
| `tests/compose/relation/test_relation_model.py` | CteItem, RelationSql, RelationCapabilities, CompiledRelation, constants |
| `tests/compose/relation/test_stable_relation_snapshot.py` | 消费 Java snapshot, 验证 contract version, schema metadata, capabilities, SQL markers, Python/Java parity |

### 更新测试
| 文件 | 变更 |
|---|---|
| `tests/compose/schema/test_schema_errors.py` | ALL_CODES 14→16 |
| `tests/compose/compilation/test_error_codes.py` | ALL_CODES 4→7 |

### 测试结果
```
focused: 333 passed in 0.36s
full regression (--ignore=tests/integration): 3330 passed in 5.86s
```

## Java Snapshot 消费

- Path: `foggy-data-mcp-bridge-wt-dev-compose/foggy-dataset-model/target/parity/_stable_relation_schema_snapshot.json`
- 验证项：
  - contractVersion == "S7a-1"
  - 12 cases (4 dialects × 3 shapes)
  - schema metadata: semanticKind, referencePolicy, valueMeaning, lineage
  - ratio columns 不包含 aggregatable
  - capabilities: supportsOuterAggregate=false, supportsOuterWindow=false
  - forbiddenSqlMarkers: "FROM (WITH"
  - Python `for_dialect()` 输出与 Java snapshot 逐字段一致

## 未开放能力 (Non-Goals)

- `supports_outer_aggregate` = false
- `supports_outer_window` = false
- 不开放 timeWindow + calculatedFields.agg
- 不开放 timeWindow + calculatedFields.windowFrame
- 不实现 named / recursive CTE
- Stage 7 runtime capability: **NOT opened**
