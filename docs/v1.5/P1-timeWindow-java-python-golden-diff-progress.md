# P1 timeWindow Java Python golden diff progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer
- purpose: 跟踪 Python timeWindow 签收后遗留项 G2 的 Java/Python golden fixture 对齐

## 基本信息

- version: v1.5 follow-up
- priority: P2
- status: ready-for-review
- source_type: post-acceptance follow-up
- owning_repo: `foggy-data-mcp-bridge-python`
- java_source_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- java_acceptance: `docs/8.3.0.beta/acceptance/P1-SemanticDSL-TimeWindow-Java-acceptance.md`
- java_followup_contract: `docs/8.4.0.beta/P2-timeWindow-calculatedFields-interaction-contract.md`
- java_followup_commit: `ba7831e feat(timeWindow): support post calculatedFields in timeWindow context`
- related_gap: G2 - Java/Python `timeWindow` golden output automation not built

## 目标

- 固化 Java 已签收/后续实现的 17 个 `timeWindow` parity fixture，作为 Python 回归输入。
- Python 正例校验输出列、窗口 frame、comparative self-join、ratio null guard 等关键 SQL 语义。
- Python 反例校验 Java 对齐错误码，避免未来两端 validator 兼容矩阵漂移。

## 开发进度

- [x] 定位 Java 实现 worktree：`foggy-data-mcp-bridge-wt-dev-compose`
- [x] 读取 Java 签收证据：`P1-SemanticDSL-TimeWindow-Java-acceptance.md`
- [x] 读取 Java parity fixture：`foggy-dataset-model/src/test/resources/parity/timeWindow/*.json`
- [x] 在 Python repo 固化 fixture snapshot：`tests/fixtures/java_time_window_parity_catalog.json`
- [x] 新增 golden catalog 测试：`tests/test_dataset_model/test_time_window_java_parity_catalog.py`
- [x] 扩展到 Java 8.5.0 `timeWindow + calculatedFields` 6 个新增 fixture

## 测试进度

- [x] `python -m pytest tests/test_dataset_model/test_time_window_java_parity_catalog.py -q`
  - result: 17 passed
  - coverage: Java 8.3.0.beta + 8.5.0.beta 17 fixture snapshot; includes 2 post-calc happy + 4 post-calc negative
- [x] `python -m pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_mcp/test_java_alignment.py -q`
  - result: 63 passed
  - coverage: existing timeWindow SQL preview, SQLite execution, MCP Java alignment
- [x] `python -m pytest tests/test_dataset_model/test_sql_quoting_and_errors.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q`
  - result: 37 passed
  - coverage: adjacent dialect quoting / error handling / conditional aggregate alignment regression

## Experience Progress

- status: N/A
- reason: 纯后端 golden fixture / SQL contract 回归，无 UI 交互。

## Execution Check-in

### Completed

- Java fixture source 已确认来自正确 worktree，而不是 `main` worktree。
- 当前 golden 测试以 Java 签收 fixture 为输入，不伪造 Java 输出。
- 正例覆盖 rolling / cumulative / comparative 三类关键 SQL 结构；反例覆盖 Java 错误码。

### Self-check

- [x] fixture snapshot 记录了 Java source repo / version / acceptance path
- [x] 未修改 Java worktree
- [x] 已按 Java 8.5.0 契约扩大到后置 scalar `timeWindow + calculatedFields`
- [x] focused tests passed
- [x] progress writeback completed after test run

## 后续

- 若 Java 后续生成稳定 SQL golden 文件，可把当前结构断言升级为逐条 normalized SQL diff。
- 若 Java 后续开放二次聚合/窗口或 targetMetrics 输入 calc field，需新增 fixture 后再对齐。
