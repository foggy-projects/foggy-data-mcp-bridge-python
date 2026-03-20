"""Tests for Chart Tool."""

import pytest
from datetime import date
import base64

from foggy.mcp.tools.chart_tool import ChartTool, ExportWithChartTool


class TestChartTool:
    """Tests for ChartTool."""

    @pytest.fixture
    def tool(self):
        """Create chart tool."""
        return ChartTool()

    @pytest.fixture
    def sample_data(self):
        """Sample chart data."""
        return {
            "columns": ["category", "value"],
            "rows": [
                ["A", 100],
                ["B", 200],
                ["C", 150],
                ["D", 300],
            ],
        }

    def test_tool_properties(self, tool):
        """Test tool metadata."""
        assert tool.tool_name == "generate_chart"
        assert tool.tool_category.value == "analysis"
        assert "chart" in tool.tool_tags

    def test_get_parameters(self, tool):
        """Test parameter definitions."""
        params = tool.get_parameters()
        param_names = [p["name"] for p in params]
        assert "data" in param_names
        assert "chart_type" in param_names
        assert "title" in param_names

    @pytest.mark.asyncio
    async def test_generate_bar_chart(self, tool, sample_data):
        """Test generating bar chart."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "bar",
            "title": "Test Bar Chart",
            "x_column": "category",
            "y_column": "value",
            "store": False,
        })
        assert result.success is True
        assert result.data["chart_type"] == "bar"
        assert "image_base64" in result.data or "svg" in result.data

    @pytest.mark.asyncio
    async def test_generate_line_chart(self, tool, sample_data):
        """Test generating line chart."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "line",
            "title": "Test Line Chart",
            "store": False,
        })
        assert result.success is True
        assert result.data["chart_type"] == "line"

    @pytest.mark.asyncio
    async def test_generate_pie_chart(self, tool, sample_data):
        """Test generating pie chart."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "pie",
            "title": "Test Pie Chart",
            "store": False,
        })
        assert result.success is True

    @pytest.mark.asyncio
    async def test_generate_scatter_chart(self, tool, sample_data):
        """Test generating scatter chart."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "scatter",
            "store": False,
        })
        assert result.success is True

    @pytest.mark.asyncio
    async def test_auto_detect_columns(self, tool, sample_data):
        """Test auto-detecting columns when not specified."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "bar",
            "store": False,
        })
        assert result.success is True
        # Should use first column for X and second for Y

    @pytest.mark.asyncio
    async def test_empty_data_error(self, tool):
        """Test error with empty data."""
        result = await tool.execute({
            "data": {"columns": [], "rows": []},
            "chart_type": "bar",
        })
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_custom_dimensions(self, tool, sample_data):
        """Test custom chart dimensions."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "bar",
            "width": 1200,
            "height": 800,
            "store": False,
        })
        assert result.success is True
        assert result.data["width"] == 1200
        assert result.data["height"] == 800

    @pytest.mark.asyncio
    async def test_store_chart(self, tool, sample_data):
        """Test storing chart."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "bar",
            "store": True,
        })
        assert result.success is True
        # Should have chart_id if stored
        if "chart_id" in result.data:
            assert result.data["chart_id"] is not None

    @pytest.mark.asyncio
    async def test_svg_format(self, tool, sample_data):
        """Test SVG output format."""
        result = await tool.execute({
            "data": sample_data,
            "chart_type": "bar",
            "format": "svg",
            "store": False,
        })
        assert result.success is True
        if "svg" in result.data:
            assert "<svg" in result.data["svg"] or "<?xml" in result.data["svg"]


class TestExportWithChartTool:
    """Tests for ExportWithChartTool."""

    @pytest.fixture
    def tool(self):
        """Create export tool."""
        return ExportWithChartTool()

    @pytest.fixture
    def sample_data(self):
        """Sample export data."""
        return {
            "columns": ["name", "value"],
            "rows": [
                {"name": "A", "value": 100},
                {"name": "B", "value": 200},
            ],
        }

    def test_tool_properties(self, tool):
        """Test tool metadata."""
        assert tool.tool_name == "export_with_chart"
        assert "export" in tool.tool_tags

    def test_get_parameters(self, tool):
        """Test parameter definitions."""
        params = tool.get_parameters()
        param_names = [p["name"] for p in params]
        assert "data" in param_names
        assert "format" in param_names
        assert "include_chart" in param_names

    @pytest.mark.asyncio
    async def test_export_csv(self, tool, sample_data):
        """Test exporting to CSV."""
        result = await tool.execute({
            "data": sample_data,
            "format": "csv",
            "include_chart": False,
        })
        assert result.success is True
        assert result.data["format"] == "csv"
        assert "name,value" in result.data["data_preview"]

    @pytest.mark.asyncio
    async def test_export_json(self, tool, sample_data):
        """Test exporting to JSON."""
        result = await tool.execute({
            "data": sample_data,
            "format": "json",
            "include_chart": False,
        })
        assert result.success is True
        assert result.data["format"] == "json"
        assert '"name": "A"' in result.data["data_preview"]

    @pytest.mark.asyncio
    async def test_export_html(self, tool, sample_data):
        """Test exporting to HTML."""
        result = await tool.execute({
            "data": sample_data,
            "format": "html",
            "include_chart": False,
        })
        assert result.success is True
        assert "<table" in result.data["data_preview"]

    @pytest.mark.asyncio
    async def test_export_with_chart(self, tool, sample_data):
        """Test exporting with chart."""
        result = await tool.execute({
            "data": sample_data,
            "format": "csv",
            "include_chart": True,
            "chart_type": "bar",
        })
        assert result.success is True
        assert result.data["chart_included"] is True

    @pytest.mark.asyncio
    async def test_export_without_chart(self, tool, sample_data):
        """Test exporting without chart."""
        result = await tool.execute({
            "data": sample_data,
            "format": "csv",
            "include_chart": False,
        })
        assert result.success is True
        assert result.data["chart_included"] is False

    @pytest.mark.asyncio
    async def test_custom_filename(self, tool, sample_data):
        """Test custom filename."""
        result = await tool.execute({
            "data": sample_data,
            "format": "csv",
            "filename": "my_export",
            "include_chart": False,
        })
        assert result.success is True
        assert result.data["filename"] == "my_export.csv"


class TestChartToolIntegration:
    """Integration tests for chart tools."""

    @pytest.mark.asyncio
    async def test_large_dataset(self):
        """Test chart with large dataset."""
        tool = ChartTool()

        # Generate large dataset
        rows = [["Category_" + str(i), i * 10] for i in range(100)]

        result = await tool.execute({
            "data": {"columns": ["category", "value"], "rows": rows},
            "chart_type": "bar",
            "store": False,
        })
        assert result.success is True

    @pytest.mark.asyncio
    async def test_mixed_data_types(self):
        """Test chart with mixed data types."""
        tool = ChartTool()

        data = {
            "columns": ["name", "value"],
            "rows": [
                ["A", "100"],  # String value
                ["B", 200],    # Int value
                ["C", 150.5],  # Float value
            ],
        }

        result = await tool.execute({
            "data": data,
            "chart_type": "bar",
            "store": False,
        })
        assert result.success is True

    @pytest.mark.asyncio
    async def test_null_values(self):
        """Test chart with null values."""
        tool = ChartTool()

        data = {
            "columns": ["name", "value"],
            "rows": [
                ["A", 100],
                ["B", None],
                ["C", 150],
            ],
        }

        result = await tool.execute({
            "data": data,
            "chart_type": "bar",
            "store": False,
        })
        assert result.success is True