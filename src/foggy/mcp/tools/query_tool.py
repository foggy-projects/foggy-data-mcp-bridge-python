"""Query Model Tool implementation."""

from typing import Any, Dict, List, Optional, ClassVar
import time

from foggy.mcp.tools.base import BaseMcpTool
from foggy.mcp_spi.tool import ToolCategory, ToolResult
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp.services.query_service import QueryService
from foggy.mcp.schema.request import QueryRequest


class QueryModelTool(BaseMcpTool):
    """Tool for executing queries against query models (QM)."""

    tool_name: ClassVar[str] = "query_model"
    tool_description: ClassVar[str] = "Execute a query against a semantic query model (QM) to retrieve data. Supports filtering, grouping, aggregation, and pagination."
    tool_category: ClassVar[ToolCategory] = ToolCategory.QUERY
    tool_tags: ClassVar[List[str]] = ["query", "data", "select"]

    def __init__(
        self,
        query_service: Optional[QueryService] = None,
        max_rows: int = 10000
    ):
        """Initialize with optional query service."""
        super().__init__()
        self._query_service = query_service
        self._max_rows = max_rows

    def set_query_service(self, service: QueryService) -> None:
        """Set the query service."""
        self._query_service = service

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "query_model",
                "type": "string",
                "required": True,
                "description": "Name of the query model to query"
            },
            {
                "name": "select",
                "type": "array",
                "required": False,
                "description": "List of columns to select",
                "items": {"type": "string"}
            },
            {
                "name": "measures",
                "type": "array",
                "required": False,
                "description": "List of measures to calculate",
                "items": {"type": "string"}
            },
            {
                "name": "where",
                "type": "string",
                "required": False,
                "description": "SQL-like WHERE clause for filtering"
            },
            {
                "name": "filters",
                "type": "array",
                "required": False,
                "description": "List of filter objects",
                "items": {"type": "object"}
            },
            {
                "name": "group_by",
                "type": "array",
                "required": False,
                "description": "List of columns to group by",
                "items": {"type": "string"}
            },
            {
                "name": "order_by",
                "type": "array",
                "required": False,
                "description": "List of order specifications",
                "items": {"type": "object"}
            },
            {
                "name": "limit",
                "type": "integer",
                "required": False,
                "description": f"Maximum rows to return (default: 100, max: {self._max_rows})",
                "default": 100
            },
            {
                "name": "offset",
                "type": "integer",
                "required": False,
                "description": "Number of rows to skip for pagination",
                "default": 0
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the query."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        # Build query request
        query_request = QueryRequest(
            query_model=arguments.get("query_model", ""),
            select=arguments.get("select", []),
            measures=arguments.get("measures", []),
            where=arguments.get("where"),
            filters=arguments.get("filters", []),
            group_by=arguments.get("group_by", []),
            order_by=arguments.get("order_by", []),
            limit=min(arguments.get("limit", 100), self._max_rows),
            offset=arguments.get("offset", 0),
        )

        # Validate
        errors = await self._query_service.validate_query(query_request)
        if errors:
            return self._error_result(f"Query validation failed: {', '.join(errors)}")

        # Execute
        try:
            start_time = time.time()
            result = await self._query_service.execute_query(query_request)
            duration_ms = (time.time() - start_time) * 1000

            return self._success_result(
                data={
                    "columns": result.columns,
                    "rows": result.rows,
                    "total_rows": result.total_rows,
                    "has_more": result.has_more,
                    "query_time_ms": result.query_time_ms,
                    "execution_time_ms": duration_ms,
                },
                message=f"Query returned {result.total_rows} rows in {duration_ms:.2f}ms"
            )

        except Exception as e:
            return self._error_result(f"Query execution failed: {str(e)}")


class ComposeQueryTool(BaseMcpTool):
    """Tool for composing complex queries with joins."""

    tool_name: ClassVar[str] = "compose_query"
    tool_description: ClassVar[str] = "Compose a complex query by combining multiple query models with joins and subqueries."
    tool_category: ClassVar[ToolCategory] = ToolCategory.QUERY
    tool_tags: ClassVar[List[str]] = ["query", "compose", "join"]

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "base_model",
                "type": "string",
                "required": True,
                "description": "Base query model for the composed query"
            },
            {
                "name": "joins",
                "type": "array",
                "required": False,
                "description": "List of join configurations",
                "items": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "type": {"type": "string", "enum": ["INNER", "LEFT", "RIGHT", "FULL"]},
                        "on": {"type": "string"}
                    }
                }
            },
            {
                "name": "select",
                "type": "array",
                "required": False,
                "description": "Columns to select (can include columns from joined models)"
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the composed query."""
        # Placeholder implementation
        return self._error_result("Compose query not yet implemented")