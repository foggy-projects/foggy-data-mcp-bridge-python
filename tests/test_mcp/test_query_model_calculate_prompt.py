"""Golden checks for CALCULATE guidance exposed to MCP clients."""

from foggy.mcp.schemas.tool_config_loader import get_tool_config_loader


def test_query_model_prompt_guides_calculate_scope_and_timewindow() -> None:
    loader = get_tool_config_loader()
    tool = loader.get_tool("dataset.query_model")

    assert tool is not None

    schema = tool.inputSchema
    calculated_desc = (
        schema["properties"]["payload"]["properties"]["calculatedFields"]["description"]
    )
    prompt_text = f"{tool.description}\n{calculated_desc}"

    assert "全局占比" in prompt_text
    assert "CALCULATE(SUM(metric), REMOVE(dim))" in prompt_text
    assert "parentShare" in prompt_text
    assert "不要改用 `ROLLUP_TO`" in prompt_text
    assert "NULLIF(CALCULATE(...), 0)" in prompt_text
    assert "同比" in prompt_text
    assert "环比" in prompt_text
    assert "累计" in prompt_text
    assert "滚动" in prompt_text
    assert "timeWindow" in prompt_text
    assert "不要使用 CALCULATE" in prompt_text or "不要用 `CALCULATE`" in prompt_text


def test_query_model_prompt_guides_native_parent_share_usage() -> None:
    loader = get_tool_config_loader()
    tool = loader.get_tool("dataset.query_model")

    assert tool is not None

    prompt_text = tool.description

    assert "salesTeam$caption" in prompt_text
    assert "salesperson$caption" in prompt_text
    assert "teamShare" in prompt_text
    assert "amountTotal" in prompt_text
    assert "sum(amountTotal)" in prompt_text
    assert "calculatedFields" in prompt_text
    assert "inline formula" in prompt_text
    assert "CALCULATE" in prompt_text


def test_query_model_prompt_guides_date_bucket_boundaries() -> None:
    loader = get_tool_config_loader()
    tool = loader.get_tool("dataset.query_model")

    assert tool is not None

    prompt_text = tool.description

    assert "DATE_TRUNC" in prompt_text
    assert "不要把 `DATE_TRUNC` 当字段名" in prompt_text
    assert "salesDate$year" in prompt_text
    assert "salesDate$month" in prompt_text
    assert "dataset.describe_model_internal" in prompt_text


def test_query_model_prompt_guides_date_difference_cutoff_filters() -> None:
    loader = get_tool_config_loader()
    tool = loader.get_tool("dataset.query_model")

    assert tool is not None

    prompt_text = tool.description

    assert "Foggy 表达式 DSL" in prompt_text
    assert "DATEDIFF(...)" in prompt_text
    assert "older than N days" in prompt_text
    assert "dateMaturity" in prompt_text
    assert "2026-04-06" in prompt_text
    assert "overdueDays" in prompt_text


def test_query_model_prompt_guides_aggregate_threshold_alias_filters() -> None:
    loader = get_tool_config_loader()
    tool = loader.get_tool("dataset.query_model")

    assert tool is not None

    prompt_text = tool.description

    assert "分组后的聚合阈值" in prompt_text
    assert "Pivot 轴成员阈值" in prompt_text
    assert "pivot.rows[*].having" in prompt_text
    assert "顶层 `slice` 只用于聚合前的数据域过滤" in prompt_text
    assert "sum(amountTotal) as totalSales" in prompt_text
    assert "totalSales > 10000" in prompt_text
    assert "amountTotal > 10000" in prompt_text
    assert "明细字段" in prompt_text
