"""Chart Tool implementation.

This module provides tools for generating charts from query results.
"""

from typing import Any, Dict, List, Optional, ClassVar
import base64
import io
import time

from foggy.mcp.tools.base import BaseMcpTool
from foggy.mcp_spi.tool import ToolCategory, ToolResult
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp.storage.adapter import ChartStorageAdapter, LocalChartStorageAdapter


class ChartTool(BaseMcpTool):
    """Tool for generating charts from data.

    This tool creates charts from query results and optionally stores them
    for later retrieval.
    """

    tool_name: ClassVar[str] = "generate_chart"
    tool_description: ClassVar[str] = "Generate a chart visualization from query data. Supports bar, line, pie, and scatter charts."
    tool_category: ClassVar[ToolCategory] = ToolCategory.ANALYSIS
    tool_tags: ClassVar[List[str]] = ["chart", "visualization", "plot"]

    def __init__(
        self,
        storage_adapter: Optional[ChartStorageAdapter] = None,
        default_width: int = 800,
        default_height: int = 600,
    ):
        """Initialize chart tool.

        Args:
            storage_adapter: Adapter for storing generated charts
            default_width: Default chart width in pixels
            default_height: Default chart height in pixels
        """
        super().__init__()
        self._storage = storage_adapter or LocalChartStorageAdapter()
        self._default_width = default_width
        self._default_height = default_height

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "data",
                "type": "object",
                "required": True,
                "description": "Data for the chart (columns and rows from query result)"
            },
            {
                "name": "chart_type",
                "type": "string",
                "required": True,
                "description": "Type of chart to generate",
                "enum": ["bar", "line", "pie", "scatter", "area", "horizontal_bar"]
            },
            {
                "name": "title",
                "type": "string",
                "required": False,
                "description": "Chart title"
            },
            {
                "name": "x_column",
                "type": "string",
                "required": False,
                "description": "Column for X-axis (or category for pie chart)"
            },
            {
                "name": "y_column",
                "type": "string",
                "required": False,
                "description": "Column for Y-axis (or value for pie chart)"
            },
            {
                "name": "series_column",
                "type": "string",
                "required": False,
                "description": "Column to create multiple series (optional)"
            },
            {
                "name": "width",
                "type": "integer",
                "required": False,
                "description": f"Chart width in pixels (default: {self._default_width})"
            },
            {
                "name": "height",
                "type": "integer",
                "required": False,
                "description": f"Chart height in pixels (default: {self._default_height})"
            },
            {
                "name": "store",
                "type": "boolean",
                "required": False,
                "description": "Whether to store the chart for later retrieval",
                "default": True
            },
            {
                "name": "format",
                "type": "string",
                "required": False,
                "description": "Output format",
                "enum": ["png", "svg", "base64"],
                "default": "base64"
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Generate the chart."""
        try:
            # Extract data
            data = arguments.get("data", {})
            if isinstance(data, dict):
                columns = data.get("columns", [])
                rows = data.get("rows", data.get("data", []))
            else:
                return self._error_result("Invalid data format")

            if not rows:
                return self._error_result("No data provided for chart")

            # Get chart configuration
            chart_type = arguments.get("chart_type", "bar")
            title = arguments.get("title", "Chart")
            x_column = arguments.get("x_column")
            y_column = arguments.get("y_column")
            series_column = arguments.get("series_column")
            width = arguments.get("width", self._default_width)
            height = arguments.get("height", self._default_height)
            store = arguments.get("store", True)
            output_format = arguments.get("format", "base64")

            # Auto-detect columns if not specified
            if not x_column and columns:
                x_column = columns[0]
            if not y_column and len(columns) > 1:
                y_column = columns[1]

            # Generate chart
            start_time = time.time()

            chart_result = self._generate_chart(
                rows=rows,
                columns=columns,
                chart_type=chart_type,
                title=title,
                x_column=x_column,
                y_column=y_column,
                series_column=series_column,
                width=width,
                height=height,
                output_format=output_format,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Build response
            response_data = {
                "chart_type": chart_type,
                "title": title,
                "width": width,
                "height": height,
                "generation_time_ms": duration_ms,
            }

            if output_format == "base64":
                response_data["image_base64"] = chart_result
            elif output_format == "svg":
                response_data["svg"] = chart_result
            else:
                response_data["image_data"] = chart_result

            # Store chart if requested
            if store and output_format == "base64":
                metadata = await self._storage.store(
                    chart_data=base64.b64decode(chart_result) if chart_result else b"",
                    metadata={
                        "chart_type": chart_type,
                        "title": title,
                        "created_at": time.time(),
                    }
                )
                response_data["chart_id"] = metadata.chart_id

            return self._success_result(
                data=response_data,
                message=f"Generated {chart_type} chart in {duration_ms:.2f}ms"
            )

        except Exception as e:
            return self._error_result(f"Chart generation failed: {str(e)}")

    def _generate_chart(
        self,
        rows: List[Any],
        columns: List[str],
        chart_type: str,
        title: str,
        x_column: Optional[str],
        y_column: Optional[str],
        series_column: Optional[str],
        width: int,
        height: int,
        output_format: str,
    ) -> str:
        """Generate the chart image.

        This is a simplified implementation that returns a placeholder.
        In production, this would use matplotlib, plotly, or a chart rendering service.
        """
        # Try to import matplotlib for actual chart generation
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            import numpy as np

            # Prepare data
            x_idx = columns.index(x_column) if x_column in columns else 0
            y_idx = columns.index(y_column) if y_column in columns else 1

            x_values = [row[x_idx] if isinstance(row, (list, tuple)) else row.get(x_column, '') for row in rows]
            y_values = [row[y_idx] if isinstance(row, (list, tuple)) else row.get(y_column, 0) for row in rows]

            # Convert y_values to numeric
            y_numeric = []
            for v in y_values:
                try:
                    y_numeric.append(float(v) if v is not None else 0)
                except (ValueError, TypeError):
                    y_numeric.append(0)

            fig, ax = plt.subplots(figsize=(width / 100, height / 100))

            if chart_type == "bar":
                ax.bar(range(len(x_values)), y_numeric)
                ax.set_xticks(range(len(x_values)))
                ax.set_xticklabels(x_values, rotation=45, ha='right')
            elif chart_type == "line":
                ax.plot(range(len(x_values)), y_numeric, marker='o')
                ax.set_xticks(range(len(x_values)))
                ax.set_xticklabels(x_values, rotation=45, ha='right')
            elif chart_type == "pie":
                ax.pie(y_numeric, labels=x_values, autopct='%1.1f%%')
            elif chart_type == "scatter":
                ax.scatter(x_values, y_numeric)
            elif chart_type == "area":
                ax.fill_between(range(len(x_values)), y_numeric, alpha=0.3)
                ax.plot(range(len(x_values)), y_numeric)
            elif chart_type == "horizontal_bar":
                ax.barh(range(len(x_values)), y_numeric)
                ax.set_yticks(range(len(x_values)))
                ax.set_yticklabels(x_values)
            else:
                ax.bar(range(len(x_values)), y_numeric)

            ax.set_title(title)
            ax.set_xlabel(x_column or "X")
            ax.set_ylabel(y_column or "Y")

            plt.tight_layout()

            # Convert to requested format
            if output_format == "svg":
                svg_buffer = io.StringIO()
                fig.savefig(svg_buffer, format='svg')
                plt.close(fig)
                return svg_buffer.getvalue()
            else:
                img_buffer = io.BytesIO()
                fig.savefig(img_buffer, format='png', dpi=100)
                plt.close(fig)
                img_buffer.seek(0)
                return base64.b64encode(img_buffer.read()).decode('utf-8')

        except ImportError:
            # matplotlib not available, return placeholder
            placeholder_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f0f0f0"/>
  <text x="{width//2}" y="{height//2 - 20}" text-anchor="middle" font-size="24" font-family="Arial">{title}</text>
  <text x="{width//2}" y="{height//2 + 20}" text-anchor="middle" font-size="16" font-family="Arial">Chart Type: {chart_type}</text>
  <text x="{width//2}" y="{height//2 + 45}" text-anchor="middle" font-size="12" font-family="Arial" fill="#666">Data points: {len(rows)}</text>
  <text x="{width//2}" y="{height - 20}" text-anchor="middle" font-size="10" font-family="Arial" fill="#999">Install matplotlib for real chart generation</text>
</svg>'''

            if output_format == "svg":
                return placeholder_svg
            else:
                return base64.b64encode(placeholder_svg.encode('utf-8')).decode('utf-8')


class ExportWithChartTool(BaseMcpTool):
    """Tool for exporting data with optional chart generation."""

    tool_name: ClassVar[str] = "export_with_chart"
    tool_description: ClassVar[str] = "Export query results to a file with optional chart visualization."
    tool_category: ClassVar[ToolCategory] = ToolCategory.ANALYSIS
    tool_tags: ClassVar[List[str]] = ["export", "chart", "download"]

    def __init__(
        self,
        chart_tool: Optional[ChartTool] = None,
    ):
        """Initialize export tool.

        Args:
            chart_tool: Chart tool for generating visualizations
        """
        super().__init__()
        self._chart_tool = chart_tool or ChartTool()

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "data",
                "type": "object",
                "required": True,
                "description": "Query result data to export"
            },
            {
                "name": "format",
                "type": "string",
                "required": False,
                "description": "Export format",
                "enum": ["csv", "json", "xlsx", "html"],
                "default": "csv"
            },
            {
                "name": "include_chart",
                "type": "boolean",
                "required": False,
                "description": "Include chart visualization",
                "default": True
            },
            {
                "name": "chart_type",
                "type": "string",
                "required": False,
                "description": "Type of chart to include",
                "enum": ["bar", "line", "pie", "scatter"],
                "default": "bar"
            },
            {
                "name": "filename",
                "type": "string",
                "required": False,
                "description": "Output filename (without extension)"
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the export."""
        data = arguments.get("data", {})
        export_format = arguments.get("format", "csv")
        include_chart = arguments.get("include_chart", True)
        chart_type = arguments.get("chart_type", "bar")
        filename = arguments.get("filename", "export")

        try:
            # Generate chart if requested
            chart_data = None
            if include_chart:
                chart_result = await self._chart_tool.execute({
                    "data": data,
                    "chart_type": chart_type,
                    "format": "base64",
                    "store": False,
                })
                if chart_result.success:
                    chart_data = chart_result.data.get("image_base64")

            # Export data
            export_result = self._export_data(data, export_format)

            response_data = {
                "format": export_format,
                "filename": f"{filename}.{export_format}",
                "data_preview": export_result[:500] if len(export_result) > 500 else export_result,
                "data_size": len(export_result),
                "chart_included": chart_data is not None,
            }

            if chart_data:
                response_data["chart_base64"] = chart_data

            return self._success_result(
                data=response_data,
                message=f"Exported {len(data.get('rows', []))} rows to {export_format}"
            )

        except Exception as e:
            return self._error_result(f"Export failed: {str(e)}")

    def _export_data(self, data: Dict[str, Any], format: str) -> str:
        """Export data to specified format."""
        import json
        import csv
        from io import StringIO

        columns = data.get("columns", [])
        rows = data.get("rows", data.get("data", []))

        if format == "json":
            # Convert to list of dicts
            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append(row)
                else:
                    result.append(dict(zip(columns, row)))
            return json.dumps(result, indent=2, ensure_ascii=False)

        elif format == "csv":
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow([row.get(col, '') for col in columns])
                else:
                    writer.writerow(row)
            return output.getvalue()

        elif format == "html":
            html = ['<table border="1">']
            html.append('<tr>' + ''.join(f'<th>{col}</th>' for col in columns) + '</tr>')
            for row in rows:
                html.append('<tr>')
                if isinstance(row, dict):
                    for col in columns:
                        html.append(f'<td>{row.get(col, "")}</td>')
                else:
                    for cell in row:
                        html.append(f'<td>{cell}</td>')
                html.append('</tr>')
            html.append('</table>')
            return '\n'.join(html)

        elif format == "xlsx":
            # Try to use openpyxl for Excel export
            try:
                from io import BytesIO
                import openpyxl

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.append(columns)
                for row in rows:
                    if isinstance(row, dict):
                        ws.append([row.get(col, '') for col in columns])
                    else:
                        ws.append(list(row))

                buffer = BytesIO()
                wb.save(buffer)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')

            except ImportError:
                # Fallback to CSV
                return self._export_data(data, "csv")

        return ""