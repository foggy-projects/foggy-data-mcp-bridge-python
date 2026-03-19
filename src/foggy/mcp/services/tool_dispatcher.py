"""Tool dispatcher for MCP server."""

from typing import Any, Callable, Dict, List, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel
import asyncio
import time

from foggy.mcp.schema.tool import ToolCallRequest, ToolCallResult, ToolDefinition, ToolCallStatus
from foggy.mcp.schema.request import McpRequestContext


class ToolFilter(BaseModel):
    """Filter for tool discovery."""

    category: Optional[str] = None
    tags: List[str] = []
    name_pattern: Optional[str] = None


class ToolCallback:
    """Callback wrapper for tool execution."""

    def __init__(
        self,
        tool_name: str,
        callback: Callable,
        definition: Optional[ToolDefinition] = None
    ):
        """Initialize callback with tool name and function."""
        self.tool_name = tool_name
        self.callback = callback
        self.definition = definition or self._create_default_definition()

    def _create_default_definition(self) -> ToolDefinition:
        """Create a default tool definition from callback signature."""
        import inspect

        sig = inspect.signature(self.callback)
        params = []

        for name, param in sig.parameters.items():
            if name in ('self', 'context', 'ctx'):
                continue

            param_def = {
                "name": name,
                "type": "string",
                "required": param.default == inspect.Parameter.empty
            }

            if param.annotation != inspect.Parameter.empty:
                type_map = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                    list: "array",
                    dict: "object"
                }
                param_def["type"] = type_map.get(param.annotation, "string")

            params.append(param_def)

        return ToolDefinition(
            name=self.tool_name,
            description=self.callback.__doc__ or f"Tool: {self.tool_name}",
            parameters=params
        )

    async def execute(self, arguments: Dict[str, Any], context: Optional[McpRequestContext] = None) -> Any:
        """Execute the tool callback."""
        import inspect

        if inspect.iscoroutinefunction(self.callback):
            return await self.callback(**arguments)
        else:
            return self.callback(**arguments)


class McpToolDispatcher:
    """Dispatcher for tool calls with registration and execution management."""

    def __init__(self, default_timeout: int = 60):
        """Initialize the dispatcher."""
        self._tools: Dict[str, ToolCallback] = {}
        self._categories: Dict[str, List[str]] = {}
        self._default_timeout = default_timeout

    def register(
        self,
        name: str,
        callback: Callable,
        definition: Optional[ToolDefinition] = None
    ) -> None:
        """Register a tool callback."""
        tool_callback = ToolCallback(name, callback, definition)
        self._tools[name] = tool_callback

        # Index by category
        category = tool_callback.definition.category
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)

    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            tool = self._tools[name]
            category = tool.definition.category
            if category in self._categories and name in self._categories[category]:
                self._categories[category].remove(name)
            del self._tools[name]
            return True
        return False

    def get_tool(self, name: str) -> Optional[ToolCallback]:
        """Get a registered tool callback."""
        return self._tools.get(name)

    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition."""
        callback = self._tools.get(name)
        return callback.definition if callback else None

    def list_tools(self, filter_: Optional[ToolFilter] = None) -> List[ToolDefinition]:
        """List registered tools, optionally filtered."""
        definitions = [cb.definition for cb in self._tools.values()]

        if filter_:
            if filter_.category:
                definitions = [d for d in definitions if d.category == filter_.category]
            if filter_.tags:
                definitions = [d for d in definitions if any(t in d.tags for t in filter_.tags)]
            if filter_.name_pattern:
                import fnmatch
                definitions = [d for d in definitions if fnmatch.fnmatch(d.name, filter_.name_pattern)]

        return definitions

    def list_categories(self) -> List[str]:
        """List available tool categories."""
        return list(self._categories.keys())

    async def dispatch(
        self,
        request: ToolCallRequest,
        context: Optional[McpRequestContext] = None
    ) -> ToolCallResult:
        """Dispatch a tool call request."""
        start_time = time.time()
        tool_name = request.tool_name

        # Find the tool
        callback = self._tools.get(tool_name)
        if not callback:
            return ToolCallResult.failure_result(
                tool_name=tool_name,
                error_message=f"Tool not found: {tool_name}",
                error_code=404
            )

        # Validate required parameters
        definition = callback.definition
        required_params = [p["name"] for p in definition.parameters if p.get("required", False)]
        missing_params = [p for p in required_params if p not in request.arguments]

        if missing_params:
            return ToolCallResult.failure_result(
                tool_name=tool_name,
                error_message=f"Missing required parameters: {missing_params}",
                error_code=400
            )

        # Execute with timeout
        timeout = request.timeout_seconds or definition.timeout_seconds or self._default_timeout

        try:
            result = await asyncio.wait_for(
                callback.execute(request.arguments, context),
                timeout=timeout
            )

            duration_ms = (time.time() - start_time) * 1000
            return ToolCallResult.success_result(
                tool_name=tool_name,
                result=result,
                duration_ms=duration_ms
            )

        except asyncio.TimeoutError:
            return ToolCallResult.timeout_result(tool_name=tool_name)

        except Exception as e:
            return ToolCallResult.failure_result(
                tool_name=tool_name,
                error_message=str(e),
                error_code=500
            )

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Export all tools in OpenAI format."""
        return [cb.definition.to_openai_tool() for cb in self._tools.values()]


def tool(
    name: Optional[str] = None,
    category: str = "general",
    description: Optional[str] = None,
    timeout: int = 60
) -> Callable:
    """Decorator for registering a function as an MCP tool."""
    def decorator(func: Callable) -> Callable:
        func._mcp_tool = True
        func._mcp_tool_name = name or func.__name__
        func._mcp_tool_category = category
        func._mcp_tool_description = description or func.__doc__ or ""
        func._mcp_tool_timeout = timeout
        return func
    return decorator