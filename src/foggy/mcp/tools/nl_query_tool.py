"""Natural Language Query Tool implementation."""

from typing import Any, Dict, List, Optional, ClassVar
import time

from foggy.mcp.tools.base import BaseMcpTool
from foggy.mcp_spi.tool import ToolCategory, ToolResult
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp.services.query_service import QueryService
from foggy.mcp.schema.query import DatasetNLQueryRequest, DatasetNLQueryResponse, QueryIntent


class NaturalLanguageQueryTool(BaseMcpTool):
    """Tool for executing natural language queries.

    This tool interprets natural language queries and translates them
    into structured queries against query models.
    """

    tool_name: ClassVar[str] = "natural_language_query"
    tool_description: ClassVar[str] = "Execute a natural language query against the semantic layer. The query is automatically interpreted and mapped to the appropriate query model and columns."
    tool_category: ClassVar[ToolCategory] = ToolCategory.QUERY
    tool_tags: ClassVar[List[str]] = ["query", "nl", "ai", "natural-language"]

    def __init__(
        self,
        query_service: Optional[QueryService] = None,
        default_model: Optional[str] = None
    ):
        """Initialize with optional query service and default model."""
        super().__init__()
        self._query_service = query_service
        self._default_model = default_model

    def set_query_service(self, service: QueryService) -> None:
        """Set the query service."""
        self._query_service = service

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions."""
        return [
            {
                "name": "query",
                "type": "string",
                "required": True,
                "description": "Natural language query text (e.g., 'Show me sales by region for last month')"
            },
            {
                "name": "query_model",
                "type": "string",
                "required": False,
                "description": "Target query model (optional, will be auto-detected if not specified)"
            },
            {
                "name": "max_rows",
                "type": "integer",
                "required": False,
                "description": "Maximum rows to return",
                "default": 100
            },
            {
                "name": "include_sql",
                "type": "boolean",
                "required": False,
                "description": "Include generated SQL in response",
                "default": False
            },
            {
                "name": "include_explanation",
                "type": "boolean",
                "required": False,
                "description": "Include query explanation",
                "default": True
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the natural language query."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        query_text = arguments.get("query")
        if not query_text:
            return self._error_result("query is required")

        query_model = arguments.get("query_model") or self._default_model

        try:
            start_time = time.time()

            # Execute NL query
            result = await self._query_service.execute_nl_query(
                query=query_text,
                query_model=query_model,
                context=arguments
            )

            duration_ms = (time.time() - start_time) * 1000

            # Build response
            response_data = {
                "query": query_text,
                "query_model": result.get("query_model"),
                "success": result.get("success", False),
                "result": result.get("result"),
                "execution_time_ms": duration_ms,
            }

            if arguments.get("include_sql"):
                response_data["sql"] = result.get("sql")

            if arguments.get("include_explanation"):
                response_data["explanation"] = result.get("explanation")

            if not result.get("success"):
                response_data["error"] = result.get("error")
                return self._error_result(
                    error_message=result.get("error", "Query failed"),
                    error_code=400
                )

            return self._success_result(
                data=response_data,
                message=f"Query executed in {duration_ms:.2f}ms"
            )

        except Exception as e:
            return self._error_result(f"Natural language query failed: {str(e)}")


class QuerySuggestionTool(BaseMcpTool):
    """Tool for suggesting queries based on natural language."""

    tool_name: ClassVar[str] = "suggest_query"
    tool_description: ClassVar[str] = "Suggest a structured query based on natural language description. Returns the suggested query structure without executing it."
    tool_category: ClassVar[ToolCategory] = ToolCategory.METADATA
    tool_tags: ClassVar[List[str]] = ["query", "suggest", "ai"]

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
                "name": "description",
                "type": "string",
                "required": True,
                "description": "Natural language description of what you want to query"
            },
            {
                "name": "model_name",
                "type": "string",
                "required": False,
                "description": "Target model (optional)"
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the query suggestion."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        description = arguments.get("description")
        model_name = arguments.get("model_name")

        if not description:
            return self._error_result("description is required")

        try:
            # Get suggestion (placeholder implementation)
            suggested_query = await self._query_service._query_expert_service.suggest_query(
                description=description,
                model_name=model_name or ""
            ) if hasattr(self._query_service, '_query_expert_service') else None

            if suggested_query:
                return self._success_result(
                    data={
                        "suggested_query": {
                            "query_model": suggested_query.query_model,
                            "select": suggested_query.select,
                            "measures": suggested_query.measures,
                            "where": suggested_query.where,
                            "group_by": suggested_query.group_by,
                            "order_by": suggested_query.order_by,
                        },
                        "description": description,
                    },
                    message="Query suggestion generated"
                )
            else:
                return self._success_result(
                    data={
                        "suggested_query": None,
                        "description": description,
                        "message": "Could not generate query suggestion. Please try a more specific description."
                    }
                )

        except Exception as e:
            return self._error_result(f"Failed to suggest query: {str(e)}")


class QueryValidationTool(BaseMcpTool):
    """Tool for validating queries before execution."""

    tool_name: ClassVar[str] = "validate_query"
    tool_description: ClassVar[str] = "Validate a query structure without executing it. Returns any validation errors or warnings."
    tool_category: ClassVar[ToolCategory] = ToolCategory.METADATA
    tool_tags: ClassVar[List[str]] = ["query", "validate"]

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
                "name": "query_model",
                "type": "string",
                "required": True,
                "description": "Name of the query model"
            },
            {
                "name": "select",
                "type": "array",
                "required": False,
                "description": "Columns to select",
                "items": {"type": "string"}
            },
            {
                "name": "where",
                "type": "string",
                "required": False,
                "description": "WHERE clause"
            },
            {
                "name": "group_by",
                "type": "array",
                "required": False,
                "description": "Group by columns",
                "items": {"type": "string"}
            },
        ]

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the validation."""
        if not self._query_service:
            return self._error_result("Query service not configured")

        from foggy.mcp.schema.request import QueryRequest

        query_request = QueryRequest(
            query_model=arguments.get("query_model", ""),
            select=arguments.get("select", []),
            where=arguments.get("where"),
            group_by=arguments.get("group_by", []),
        )

        try:
            errors = await self._query_service.validate_query(query_request)

            return self._success_result(
                data={
                    "valid": len(errors) == 0,
                    "errors": errors,
                    "query_model": query_request.query_model,
                },
                message="Query is valid" if not errors else f"Validation failed: {', '.join(errors)}"
            )

        except Exception as e:
            return self._error_result(f"Validation failed: {str(e)}")