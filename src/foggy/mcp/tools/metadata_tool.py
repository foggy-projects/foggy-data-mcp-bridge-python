"""Metadata Tool implementation."""

from typing import Any, Dict, List, Optional, ClassVar

from foggy.mcp.tools.base import BaseMcpTool
from foggy.mcp_spi.tool import ToolCategory, ToolResult
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp.services.query_service import QueryService


class MetadataTool(BaseMcpTool):
    """Tool for retrieving model metadata and schema information."""

    tool_name: ClassVar[str] = "get_metadata"
    tool_description: ClassVar[str] = "Retrieve metadata and schema information for a query model, including available columns, measures, dimensions, and supported operations."
    tool_category: ClassVar[ToolCategory] = ToolCategory.METADATA
    tool_tags: ClassVar[List[str]] = ["metadata", "schema", "model"]

    def __init__(self, query_service: Optional[QueryService] = None):
        """Initialize with optional query service."""
        super().__init__()
        self._query_service = query_service

    def set_query_service(self, service: QueryService) -> None:
        """Set the query service."""
        self._query_service = service

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "model_name",
                "type": "string",
                "required": True,
                "description": "Name of the model to get metadata for"
            },
            {
                "name": "include_columns",
                "type": "boolean",
                "required": False,
                "description": "Include column information",
                "default": True
            },
            {
                "name": "include_measures",
                "type": "boolean",
                "required": False,
                "description": "Include measure information",
                "default": True
            },
            {
                "name": "include_dimensions",
                "type": "boolean",
                "required": False,
                "description": "Include dimension information",
                "default": True
            },
            {
                "name": "include_examples",
                "type": "boolean",
                "required": False,
                "description": "Include AI query examples",
                "default": False
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the metadata query."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        model_name = arguments.get("model_name")
        if not model_name:
            return self._error_result("model_name is required")

        try:
            schema = await self._query_service.get_model_schema(model_name)

            # Apply filters based on parameters
            result = {
                "name": schema.get("name", model_name),
                "alias": schema.get("alias"),
                "description": schema.get("description"),
                "model_type": schema.get("model_type", "query_model"),
            }

            if arguments.get("include_columns", True):
                result["columns"] = schema.get("columns", [])

            if arguments.get("include_measures", True):
                result["measures"] = schema.get("measures", [])

            if arguments.get("include_dimensions", True):
                result["dimensions"] = schema.get("dimensions", [])

            if arguments.get("include_examples", False):
                result["ai_description"] = schema.get("ai_description")
                result["ai_examples"] = schema.get("ai_examples", [])

            return self._success_result(
                data=result,
                message=f"Metadata retrieved for model: {model_name}"
            )

        except Exception as e:
            return self._error_result(f"Failed to get metadata: {str(e)}")


class ListModelsTool(BaseMcpTool):
    """Tool for listing available query models."""

    tool_name: ClassVar[str] = "list_models"
    tool_description: ClassVar[str] = "List all available query models (QM) and table models (TM) that can be queried."
    tool_category: ClassVar[ToolCategory] = ToolCategory.METADATA
    tool_tags: ClassVar[List[str]] = ["metadata", "list", "models"]

    def __init__(self, query_service: Optional[QueryService] = None):
        """Initialize with optional query service."""
        super().__init__()
        self._query_service = query_service

    def set_query_service(self, service: QueryService) -> None:
        """Set the query service."""
        self._query_service = service

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "filter",
                "type": "string",
                "required": False,
                "description": "Filter pattern for model names (supports wildcards)"
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the list models query."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        try:
            models = await self._query_service.get_available_models()

            # Apply filter if provided
            filter_pattern = arguments.get("filter")
            if filter_pattern:
                import fnmatch
                models = [m for m in models if fnmatch.fnmatch(m, filter_pattern)]

            return self._success_result(
                data={
                    "models": models,
                    "count": len(models),
                },
                message=f"Found {len(models)} available models"
            )

        except Exception as e:
            return self._error_result(f"Failed to list models: {str(e)}")


class DescriptionModelTool(BaseMcpTool):
    """Tool for getting detailed model descriptions for AI/LLM context."""

    tool_name: ClassVar[str] = "describe_model"
    tool_description: ClassVar[str] = "Get a detailed description of a model optimized for AI/LLM understanding, including natural language descriptions and example queries."
    tool_category: ClassVar[ToolCategory] = ToolCategory.METADATA
    tool_tags: ClassVar[List[str]] = ["metadata", "ai", "description"]

    def __init__(self, query_service: Optional[QueryService] = None):
        """Initialize with optional query service."""
        super().__init__()
        self._query_service = query_service

    def set_query_service(self, service: QueryService) -> None:
        """Set the query service."""
        self._query_service = service

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "model_name",
                "type": "string",
                "required": True,
                "description": "Name of the model to describe"
            },
            {
                "name": "format",
                "type": "string",
                "required": False,
                "description": "Output format: 'markdown', 'json', or 'text'",
                "enum": ["markdown", "json", "text"],
                "default": "markdown"
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the model description query."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        model_name = arguments.get("model_name")
        if not model_name:
            return self._error_result("model_name is required")

        format_type = arguments.get("format", "markdown")

        try:
            schema = await self._query_service.get_model_schema(model_name)

            if format_type == "json":
                return self._success_result(data=schema)

            # Generate description
            lines = []
            lines.append(f"# Model: {schema.get('name', model_name)}")
            lines.append("")

            if schema.get("alias"):
                lines.append(f"**Display Name:** {schema['alias']}")
                lines.append("")

            if schema.get("description"):
                lines.append(f"**Description:** {schema['description']}")
                lines.append("")

            if schema.get("ai_description"):
                lines.append("## AI Description")
                lines.append(schema["ai_description"])
                lines.append("")

            # Columns
            columns = schema.get("columns", [])
            if columns:
                lines.append("## Columns")
                lines.append("")
                lines.append("| Name | Type | Description |")
                lines.append("|------|------|-------------|")
                for col in columns:
                    name = col.get("name", "")
                    col_type = col.get("type", "string")
                    desc = col.get("description", "")
                    lines.append(f"| {name} | {col_type} | {desc} |")
                lines.append("")

            # Measures
            measures = schema.get("measures", [])
            if measures:
                lines.append("## Measures")
                lines.append("")
                for m in measures:
                    name = m.get("name", "")
                    agg = m.get("aggregation", "")
                    desc = m.get("description", "")
                    lines.append(f"- **{name}** ({agg}): {desc}")
                lines.append("")

            # Dimensions
            dimensions = schema.get("dimensions", [])
            if dimensions:
                lines.append("## Dimensions")
                lines.append("")
                for d in dimensions:
                    name = d.get("name", "")
                    dim_type = d.get("type", "regular")
                    lines.append(f"- **{name}** ({dim_type})")
                lines.append("")

            # Examples
            examples = schema.get("ai_examples", [])
            if examples:
                lines.append("## Example Queries")
                lines.append("")
                for i, ex in enumerate(examples, 1):
                    lines.append(f"{i}. {ex}")
                lines.append("")

            description = "\n".join(lines)

            return self._success_result(
                data={
                    "description": description,
                    "format": format_type,
                    "model_name": model_name,
                },
                message=f"Model description generated for: {model_name}"
            )

        except Exception as e:
            return self._error_result(f"Failed to describe model: {str(e)}")