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
    assert "组内/父级占比" in prompt_text or "父级/组内占比" in prompt_text
    assert "CALCULATE(SUM(metric), REMOVE(childDim))" in prompt_text
    assert "NULLIF(CALCULATE(...), 0)" in prompt_text
    assert "同比" in prompt_text
    assert "环比" in prompt_text
    assert "累计" in prompt_text
    assert "滚动" in prompt_text
    assert "timeWindow" in prompt_text
    assert "不要使用 CALCULATE" in prompt_text or "不要用 `CALCULATE`" in prompt_text
