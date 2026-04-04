# P0-Odoo 本地模型注册中心消费契约-需求

## 基本信息

- 目标版本：`v1.0`
- 需求等级：`P0`
- 状态：`待处理`
- 责任项目：`foggy-data-mcp-bridge-python`

## 背景

Odoo TM/QM 模型的唯一来源后续将收口到独立 private authority 仓，并先通过 workspace 内的独立模块 `foggy-model-registry` 向消费仓发布 bundle。

Python 侧当前同样面临：

- 模型副本位于仓内目录
- 更新需要手工同步
- 测试 / 调试路径容易与 authority 漂移

本阶段 Python 侧只需要遵守统一消费契约，不承担 marketplace、计费或对外服务职责。

## 问题定义

Python 侧需要解决的是：

- 如何按 lock 文件拉取固定版本模型
- 如何在本地调试时保持 bundle 可复现
- 如何让 CI 阻止手工修改模型副本

如果继续依赖人工复制目录和可变 `latest`，就无法保证 authority 真正唯一。

## 目标

- Python 只消费 registry 发布的 bundle
- Python 使用 lock 文件固定版本和 checksum
- Python CI 校验模型目录与 lock 一致
- Python 不再向外扩散“手改模型副本”的工作方式

## 最小消费契约

### 1. 输入

Python 侧只认以下信息：

- `registry`
- `package`
- `version`
- `checksum`

如以 `channel` 触发拉取，必须先解析到具体版本，再写 lock。

### 2. lock 文件

```json
{
  "registry": "http://127.0.0.1:9401",
  "package": "foggy.odoo.pro",
  "version": "1.1.0",
  "checksum": "sha256:..."
}
```

### 3. 授权规则

- `community`：允许匿名拉取
- `pro`：必须携带 `FOGGY_MODEL_KEY`
- Python 不自行定义另一套授权协议，只复用 registry 统一规则

### 4. staging 规则

允许保留本地 staging 模型目录，但必须是：

- 脚本生成
- 可删除重建
- 受 lock 文件约束

## 任务拆分

### 1. Python 消费入口

- 增加 `pull-models` 或等效脚本入口
- 支持从 lock 文件拉取和解包 bundle
- 将现有启动脚本收口到统一模型目录参数
- 统一面向 `foggy-model-registry` 消费，而不是面向 Odoo 仓目录

### 2. Python CI

- 增加 lock 校验
- 增加 checksum 校验
- 增加“工作区模型目录是否与 lock 一致”的漂移检查

### 3. Python 目录治理

- 仓内若保留 staging 模型目录，需标记为 generated
- 禁止继续手改模型副本并把其当源码提交

## 验收标准

- Python 侧能够通过 lock 文件拉取 Odoo community/pro bundle
- pro 无 key 时拉取失败
- lock 文件与本地模型目录不一致时，CI 明确失败
- Python 侧能在不破坏现有调试入口的情况下切换到 bundle 消费

## 非目标

- 本条不负责 authority 仓拆分
- 本条不负责 key 发放后台实现
- 本条不要求 Python 侧现在支持对外 registry 服务

## 关联文档

- Odoo：`foggy-odoo-bridge-pro/docs/prompts/v1.1/P0-07-local-model-registry-min-spec.md`
- Java：`foggy-data-mcp-bridge/docs/8.1.10.beta/P0-Odoo本地模型注册中心消费契约-需求.md`

## 跟踪维度

- 开发进度：`待开始`
- 测试进度：`待开始`
- 体验进度：`N/A`
