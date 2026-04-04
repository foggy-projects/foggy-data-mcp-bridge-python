# P0-Odoo 本地模型注册中心消费契约 — Implementation Plan

## 基本信息

- 目标版本：`v1.0`
- 上游需求：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-需求.md`
- 代码清单：`docs/v1.0/P0-Odoo本地模型注册中心消费契约-code-inventory.md`
- 仓库：`foggy-data-mcp-bridge-python`

## 前置条件

- `foggy-model-registry` Stage 1 已完成（publish / pull 可用）
- `foggy-odoo-bridge-pro` Stage 2 已完成（model-manifest.json 已确认）
- registry 已发布至少一个 community bundle

## 实施步骤

### Step 1. 创建 pull 脚本

在 `scripts/pull-odoo-models.py` 创建拉取入口：

1. 读取 lock 文件（如存在）
2. 通过 HTTP 或本地路径从 registry 拉取 bundle
3. 校验 sha256 checksum
4. 解包到 `src/foggy/demo/models/odoo/`
5. 写/更新 `models.lock.json`

支持参数：
- `--registry <url-or-path>`（默认 `../foggy-model-registry/data`）
- `--channel <stable|beta>`（默认 `stable`）
- `--edition <community|pro>`
- `--key <value>`（pro 时必需）
- `--output <dir>`（默认 `src/foggy/demo/models/odoo/`）

验收：运行后模型目录与 registry bundle 一致，lock 文件已更新。

### Step 2. 创建 lock 文件初始版本

手动运行一次 pull，生成首个 `models.lock.json`，提交到 git。

验收：lock 文件存在且内容完整。

### Step 3. 创建 CI 漂移校验脚本

在 `scripts/check-model-drift.py` 创建校验入口：

1. 读取 lock 中的 checksum
2. 对模型目录计算实际 sha256
3. 比对；不一致时退出非零

验收：
- 未修改时通过
- 手改任意 TM/QM 后失败

### Step 4. 标记模型目录为 generated

在 `src/foggy/demo/models/odoo/` 下添加 `GENERATED.md`：

```
本目录由 foggy-model-registry 同步生成，禁止手工修改。
使用 scripts/pull-odoo-models.py 更新。
```

验收：文件存在。

### Step 5. 兼容性确认

只读分析确认：

1. `load_models_from_directory()` 兼容 pull 后的目录结构
2. `start_python_mcp.py` 的模型目录参数可指向 pull 后的目录
3. 现有测试不受影响

验收：`python scripts/run_fast_tests.py -q` 全部通过。

## 不做的事

- 不修改模型加载引擎
- 不在 CI 中自动 pull
- 不删除现有模型文件
- 不修改 `value` 契约（那是另一条需求线）

## 预估工作量

| Step | 预估 | 说明 |
|------|------|------|
| 1. pull 脚本 | 30 min | Python 脚本 |
| 2. 初始 lock | 5 min | 运行一次 pull |
| 3. 漂移校验 | 15 min | checksum 比对 |
| 4. GENERATED 标记 | 5 min | 文档 |
| 5. 兼容确认 | 15 min | 只读分析 + 测试 |
| **合计** | **~1h 10min** | |
