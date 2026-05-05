# P1 BUG: timeRole / recommendedUse 元数据未进入 LLM 可见契约

## 文档作用

- doc_type: bug
- intended_for: execution-agent | reviewer | signoff-owner
- purpose: 记录 TM 中已存在的时间语义元数据没有被 `dataset.describe_model_internal` 和 timeWindow 校验链路消费，导致 LLM 按不可见契约猜测日期字段的问题。

## 基本信息

- version: v1.6
- priority: P1
- severity: benchmark-semantic-regression
- status: ready-for-review
- source type: acceptance-found issue / benchmark-regression
- owner: foggy-data-mcp-bridge-python
- downstream sync owner: foggy-odoo-bridge-pro vendored `foggy_mcp_pro/lib/foggy`

## 背景

Odoo TM 中已经存在字段级语义：

- `timeRole: 'business_date'`
- `recommendedUse: 'Primary ... business date ...'`

但 AR-011 benchmark 中 LLM 仍反复尝试 `year`、`createDate$year`、`move$date$year` 和非法 `timeWindow`。这说明 LLM 没有在模型详情中看到可执行的日期语义，或者看到了工具提示但无法从 `describe_model_internal` 里找到对应字段。

当前 `compose_script` 工具说明已经要求使用 `timeRole=business_date` 的字段作为主时间轴；但 `dataset.describe_model_internal` 的 markdown 输出并没有渲染 `timeRole` / `recommendedUse`。这是提示词契约与模型详情响应之间的不一致。

## 问题陈述

### BUG-1: describe_model_internal 未渲染字段级 timeRole / recommendedUse

`_build_single_model_markdown` 目前只输出：

- model `description`
- dimension join 的 `description` / `key_description`
- dimension property 的 `description`
- fact column 的 `comment`
- measure / formula 的 `description`

它没有输出 `timeRole`、`recommendedUse` 这类 extra metadata。结果是 TM 作者已经写入的字段语义对 LLM 不可见。

### BUG-2: timeWindow 校验未识别 property-level timeRole

`collect_time_window_field_sets` 目前只把以下字段加入 time fields：

- `dim.is_time_dimension()` 的裸 dimension / `$id`
- 名称或描述包含 `date` 的 join 自身 `$id`

但 `move$date` 属于 `move` join 的 property，不是 `dim_date` 时间维，也不是 join 自身 `$id`。即使 property 上带有 `timeRole: 'business_date'`，当前校验也不会把 `move$date` 当作合法 timeWindow 字段。

## 目标结果

- `dataset.describe_model_internal` 能把字段级 `timeRole` / `recommendedUse` 以紧凑、稳定、LLM 可读的方式输出。
- `timeWindow` 字段集合能识别受支持的 property-level 时间字段，至少覆盖带 `timeRole` 的日期属性。
- 工具提示中的 `timeRole=business_date` 要求与模型详情实际输出一致。
- 下游 Odoo vendored Python 引擎同步同一行为，避免 Python 源码修复后 Odoo 内嵌模式仍旧失效。

## 任务拆分 / Ownership

- Python source engine:
  - `src/foggy/dataset_model/semantic/service.py`
  - `src/foggy/dataset_model/semantic/time_window.py`
  - metadata markdown / JSON response contract tests
- Odoo vendored runtime:
  - `foggy_mcp_pro/lib/foggy/dataset_model/semantic/service.py`
  - `foggy_mcp_pro/lib/foggy/dataset_model/semantic/time_window.py`
  - vendored sync / Odoo embedded contract tests
- Odoo benchmark metadata:
  - 由 Odoo workitem 记录 AR-011 / AR-012 业务语义补强，不在本 BUG 文档中展开。

## Acceptance Criteria

- `describe_model_internal` 对含 `timeRole: 'business_date'` / `recommendedUse` 的字段输出可见标记。
- 输出格式不会破坏既有 markdown 表格解析和字段名白名单。
- `timeWindow.field` 可使用明确支持的字段；如果某字段只适合普通 date range 而不适合 timeWindow，应在响应中明确说明。
- `compose_script` 中关于 `timeRole=business_date` 的提示不再引用 LLM 看不到的契约。
- Odoo vendored 引擎与 Python source 行为一致。

## 约束 / 非目标

- 不把任意包含 `date` 的普通字符串字段都放宽为 timeWindow 字段。
- 不接受 LLM 自造 `field$year` / `field$month` / SQL 函数字段。
- 不在本 BUG 中定义 Odoo AR-012 的“核销率”业务口径。
- 不要求一次性改造完整 TM schema；若 extra metadata 已可稳定读取，可先最小渲染。

## Progress Tracking

- development: completed ✅
- testing: completed ✅ (14/14 new targeted tests pass, 0 regressions in required regression suite)
- experience: N/A，纯后端 metadata / prompt contract 变更，无 UI 体验变更。

## Execution Check-in (2026-05-05)

### Changed Files

**Python source (`foggy-data-mcp-bridge-python`)**:
- `src/foggy/dataset_model/semantic/service.py`
  - Added `_get_time_role_hint(obj)` static helper (reads `timeRole` / `recommendedUse` from Pydantic `model_extra` with `getattr` fallback)
  - `_build_single_model_markdown`: join property rows now append `[timeRole=…; recommendedUse=…]` to the Description cell when present; fact-table column rows receive the same treatment
  - `_build_multi_model_markdown`: join property sub-lines now append `| timeRole=… …` when the property carries a `timeRole`
  - Pipes in `recommendedUse` strings are replaced with fullwidth ｜ (`｜`) to keep markdown table cells valid

- `src/foggy/dataset_model/semantic/time_window.py`
  - Added `_has_time_role(obj)` helper — reads `timeRole` from Pydantic extra / getattr
  - Added `_is_date_type(column_type)` and `_is_date_type_str(data_type: str)` helpers with frozenset `{date, day, datetime, timestamp}`
  - `collect_time_window_field_sets`: for each join property with `_has_time_role` + `_is_date_type_str`, add `join.name$prop_name` to `time_fields`
  - `collect_time_window_field_sets`: for each fact-table column with `_has_time_role` + `_is_date_type`, add it to `time_fields`

**New test file**:
- `tests/test_mcp/test_time_role_metadata_contract.py` — 14 focused tests covering BUG-1 and BUG-2

**Vendored sync (`foggy-odoo-bridge-pro`)**:
- `foggy_mcp_pro/lib/foggy/dataset_model/semantic/service.py` — direct copy of source
- `foggy_mcp_pro/lib/foggy/dataset_model/semantic/time_window.py` — direct copy of source

### Rendering Format

Dimension join property example (single-model markdown table):

```
| move$date | Accounting Date | DAY | - | [timeRole=business_date; recommendedUse=Primary payment business date for payment trend and period pivot queries.] |
```

Fact-table column example:

```
| invoice_date | Invoice Date | Date (yyyy-MM-dd) | [timeRole=business_date; recommendedUse=Primary invoice/bill business date for timeWindow, revenue, AP, and period pivot queries.] |
```

Multi-model listing example:

```
    - [field:move$date] | Accounting Date | timeRole=business_date; recommendedUse=Primary payment...
```

### timeWindow Support Boundary

A join property field (`join$prop`) is accepted as a `timeWindow.field` when **both**:
1. The property declares a non-empty `timeRole` (via Pydantic extra).
2. The property `data_type` is one of: `DAY`, `DATE`, `DATETIME`, `TIMESTAMP` (case-insensitive).

Synthetic suffixes (`move$date$year`, `move$date$month`) remain invalid — they are not present in `available_fields` and will fail `FIELD_NOT_FOUND`.

A field without `timeRole` (e.g. `create_date`) remains outside `time_fields` and fails `FIELD_NOT_TIME` for timeWindow.

### Tests Run and Results

```powershell
python -m pytest tests\test_mcp\test_time_role_metadata_contract.py -q
# 14 passed

python -m pytest tests\test_mcp\test_list_models_tool.py tests\test_mcp\test_mcp_rpc_router.py tests\test_mcp\test_time_role_metadata_contract.py -q
# 39 passed

cd D:\foggy-projects\foggy-data-mcp\foggy-odoo-bridge-pro
python -m pytest tests\contract\test_embedded_backend_contracts.py -q
# 14 passed
```

### Risks / Follow-up

- `test_tool_config_includes_compose_script` regression is resolved by restoring the Chinese `不要直接 .execute()` guidance in `compose_script_m2.md`.
- AR-011 benchmark still needs live Odoo integration run to confirm LLM no longer guesses synthetic date fields.
- `move$date` now accepted as timeWindow.field for rolling/cumulative comparisons; comparative (`yoy` with grain=month) still requires `move$date$month` to be in available_fields. If LLM tries `yoy + month` on a payment model lacking time-dimension properties, it will get `TIMEWINDOW_GRAIN_FIELD_NOT_FOUND`. This is correct fail-closed behaviour, and can be addressed by adding calendar properties to the `move` join if needed.

### Implementation Self-Check

- **Mode**: self-check-only; no formal quality-gate document required for this narrow metadata contract fix.
- **Scope Conformance**: Source renderer, timeWindow field collection, compose tool description, tests, and Odoo vendored sync are aligned with this BUG. No unrelated source rollback was performed.
- **Decision**: ready-for-review; Odoo live benchmark remains the only external verification gap.

## Required Verification

```powershell
cd D:\foggy-projects\foggy-data-mcp\foggy-data-mcp-bridge-python
python -m pytest tests\test_mcp\test_list_models_tool.py tests\test_mcp\test_mcp_rpc_router.py -q
```

下游 Odoo vendored 同步后还需要运行 Odoo embedded backend contract / benchmark 相关测试。

## Review / Acceptance Workflow

- 代码完成后先做 execution-checkin，记录实际渲染格式、timeWindow 支持边界和测试状态。
- 如果改动触达通用 metadata contract，进入 `foggy-implementation-quality-gate`。
- Odoo AR benchmark 验证由 Odoo workitem 接续记录。
