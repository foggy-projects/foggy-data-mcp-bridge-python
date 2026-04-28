# Backlog — 版本未定的规划

存放已确认需要做但尚未确定版本的改进规划。

当某项规划确定目标版本后，移动到 `docs/<version>/` 目录下。

## 当前条目

| 编号 | 标题 | 来源 | 优先级 | 状态 |
|------|------|------|--------|------|
| B-01 | Python gateway response 格式对齐 Java pagination | P0-08 Phase 4 | 中 | ✅ 已修复 — `from_legacy()` 填充 `PaginationInfo`，service 层透传 start/limit |
| B-02 | Partner country JSONB caption embedded 引擎修复 | P0-08 Phase 3 | 低 | ✅ 已修复 — `captionDef` + `dialectFormulaDef` builder 加载与解析链路打通 |
| B-03 | v1.3 引擎收紧裸 dimension 引用 + 修复 `dimension AS alias` 静默丢列 | G5 PR-P2 复盘（`cf2ba9b` → `352a8bb`） | P0 | ✅ **resolved**（2026-04-28 · Python `v1.7` `accepted` 59176f2 · Java `8.4.0.beta` `accepted-with-risks` 4f2f48c · 详见各仓 acceptance）|
