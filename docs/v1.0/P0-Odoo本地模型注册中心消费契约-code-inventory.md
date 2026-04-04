# P0-Odoo 本地模型注册中心消费契约 — Code Inventory

## 基本信息

- 目标版本：`v1.0`
- 上游需求：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-需求.md`
- 仓库：`foggy-data-mcp-bridge-python`

## 当前 Odoo 模型位置

Python 侧 Odoo TM/QM 当前位于 `src/foggy/demo/models/odoo/`，包含 14 TM + 14 QM，作为 demo 模型随源码分发。

## Code Inventory

### Odoo 模型目录（现有）

- repo: `foggy-data-mcp-bridge-python`
- path: `src/foggy/demo/models/odoo/`
- role: 当前 Odoo TM/QM 存放位置（demo 目录）
- expected change: `update`
- notes: 后续由 pull 脚本从 registry 同步覆盖；需标记为 generated，禁止手改

### pull 脚本

- repo: `foggy-data-mcp-bridge-python`
- path: `scripts/pull-odoo-models.py`
- role: 从 registry 拉取 Odoo bundle 的入口脚本
- expected change: `create`
- notes: 直接用 Python 实现（复用 registry pull 逻辑或 HTTP 拉取）；输出到 staging 目录；写 lock 文件

### lock 文件

- repo: `foggy-data-mcp-bridge-python`
- path: `src/foggy/demo/models/odoo/models.lock.json`
- role: 锁定当前消费的 bundle 版本和 checksum
- expected change: `create`
- notes: 提交到 git；CI 校验此文件与实际模型目录一致

### CI 漂移校验脚本

- repo: `foggy-data-mcp-bridge-python`
- path: `scripts/check-model-drift.py`
- role: CI 阶段校验模型目录与 lock 文件一致性
- expected change: `create`
- notes: 比对 lock 中的 checksum 与实际模型目录 checksum

### 模型加载入口（现有）

- repo: `foggy-data-mcp-bridge-python`
- path: `src/foggy/dataset_model/`
- role: TM/QM 模型加载引擎
- expected change: `read-only-analysis`
- notes: 确认 `load_models_from_directory()` 兼容 registry pull 后的目录结构

### Odoo 启动脚本（现有）

- repo: `foggy-data-mcp-bridge-python`
- path: `scripts/start_python_mcp.py`
- role: Odoo MCP Python 独立服务启动入口
- expected change: `read-only-analysis`
- notes: 确认模型目录参数可指向 pull 后的 staging 目录
