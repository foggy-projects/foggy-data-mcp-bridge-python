# P0-Odoo 本地模型注册中心消费契约 — Execution Prompt

## 基本信息

- 目标版本：`v1.0`
- 上游文档：
  - 需求：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-需求.md`
  - 代码清单：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-code-inventory.md`
  - 实施计划：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-implementation-plan.md`
- 进度报告模板：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-progress.md`

## 开工提示词

你现在负责在 `foggy-data-mcp-bridge-python` 仓库中实现 Python 侧的 registry 消费契约。

### 你需要先读的文档

1. `docs/v1.0/P0-Odoo本地模型注册中心消费契约-需求.md` — 目标和验收标准
2. `docs/v1.0/P0-Odoo本地模型注册中心消费契约-code-inventory.md` — 代码触点
3. `docs/v1.0/P0-Odoo本地模型注册中心消费契约-implementation-plan.md` — 步骤和顺序

### 你需要做的事

按 implementation plan 的 Step 1-5 顺序执行：

1. **创建 `scripts/pull-odoo-models.py`**：从 registry 拉取 bundle 到模型目录
   - 纯 Python 标准库实现，不引入外部依赖
   - 默认 registry 路径：`../foggy-model-registry/data`
   - 解包到 `src/foggy/demo/models/odoo/`
   - 写 `models.lock.json`
   - 支持 `--edition community|pro`、`--channel stable|beta`、`--key <value>`

2. **生成初始 lock 文件**：运行一次 pull，提交 `models.lock.json`

3. **创建 `scripts/check-model-drift.py`**：比对 lock checksum 与实际目录 checksum
   - 使用与 registry publish 相同的 sha256 算法
   - 不一致时输出差异并退出非零

4. **添加 GENERATED 标记**：在模型目录下添加 `GENERATED.md`

5. **兼容性确认**：确认 `load_models_from_directory()` 和启动脚本兼容

### 你不需要做的事

- 不修改模型加载引擎
- 不在 CI 中自动 pull
- 不修改 `value` 契约（那是独立需求线 `P0-DSL切片list算子value契约收口`）
- 不在 commit 钩子中自动拉取

### 验收方式

```bash
# 1. 从 registry 拉取 community bundle
python scripts/pull-odoo-models.py \
  --registry ../foggy-model-registry/data \
  --channel stable \
  --edition community

# 2. 确认 lock 文件
cat src/foggy/demo/models/odoo/models.lock.json

# 3. 漂移校验 — 未修改时应通过
python scripts/check-model-drift.py

# 4. 手动改一个 TM 文件 → 漂移校验应失败
echo "# test" >> src/foggy/demo/models/odoo/model/OdooSaleOrderModel.tm
python scripts/check-model-drift.py
# 期望：exit 1

# 5. 恢复后测试验证
git checkout -- src/foggy/demo/models/odoo/model/OdooSaleOrderModel.tm
python scripts/run_fast_tests.py -q
```

### 执行完成后

创建 `docs/v1.0/P0-Odoo本地模型注册中心消费契约-progress.md`，按模板格式填写完成状态。
