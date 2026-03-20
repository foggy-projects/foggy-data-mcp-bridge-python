"""MCP Tool Dispatcher for routing tool calls.

This module provides the dispatcher that routes incoming tool calls
to the appropriate registered tools.
"""

from typing import Any, Dict, List, Optional
import asyncio
import time

from foggy.mcp.tools.base import ToolRegistry, BaseMcpTool
from foggy.mcp_spi.tool import ToolResult
from foggy.mcp_spi.context import ToolExecutionContext


class ToolCallRecord:
    """Record of a tool call for auditing and debugging."""

    def __init__(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None,
    ):
        """Initialize the record."""
        self.tool_name = tool_name
        self.arguments = arguments
        self.context = context
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.result: Optional[ToolResult] = None
        self.error: Optional[str] = None

    def complete(self, result: ToolResult) -> None:
        """Mark the call as complete."""
        self.end_time = time.time()
        self.result = result

    def fail(self, error: str) -> None:
        """Mark the call as failed."""
        self.end_time = time.time()
        self.error = error

    @property
    def duration_ms(self) -> Optional[float]:
        """Get the duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "toolName": self.tool_name,
            "arguments": self.arguments,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "durationMs": self.duration_ms,
            "success": self.result.is_success() if self.result else False,
            "error": self.error,
        }


class McpToolDispatcher:
    """Dispatcher for routing tool calls to registered tools.

    Handles tool registration, call routing, and execution tracking.

    Example:
        >>> dispatcher = McpToolDispatcher()
        >>> dispatcher.register_tool(my_tool)
        >>> result = await dispatcher.dispatch("query_model", {"model": "users"})
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        default_timeout: float = 60.0,
        max_concurrent_calls: int = 10,
    ):
        """Initialize the dispatcher.

        Args:
            registry: Tool registry (creates new one if None)
            default_timeout: Default timeout for tool execution in seconds
            max_concurrent_calls: Maximum concurrent tool calls
        """
        self._registry = registry or ToolRegistry()
        self._default_timeout = default_timeout
        self._max_concurrent_calls = max_concurrent_calls
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._call_history: List[ToolCallRecord] = []
        self._max_history = 1000

    def register_tool(self, tool: BaseMcpTool) -> None:
        """Register a tool.

        Args:
            tool: Tool to register
        """
        self._registry.register(tool)

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool.

        Args:
            name: Tool name

        Returns:
            True if tool was unregistered
        """
        return self._registry.unregister(name)

    def get_tool(self, name: str) -> Optional[BaseMcpTool]:
        """Get a registered tool.

        Args:
            name: Tool name

        Returns:
            Tool or None if not found
        """
        return self._registry.get(name)

    def list_tools(self) -> List[BaseMcpTool]:
        """List all registered tools.

        Returns:
            List of tools
        """
        return self._registry.list_tools()

    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names
        """
        return [t.name for t in self._registry.list_tools()]

    async def dispatch(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None,
        timeout: Optional[float] = None,
    ) -> ToolResult:
        """Dispatch a tool call to the appropriate tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            context: Execution context
            timeout: Timeout in seconds (uses default if None)

        Returns:
            ToolResult from the tool execution
        """
        # Create call record
        record = ToolCallRecord(tool_name, arguments, context)
        self._add_to_history(record)

        # Find tool
        tool = self._registry.get(tool_name)
        if tool is None:
            error = f"Tool '{tool_name}' not found. Available tools: {self.get_tool_names()}"
            record.fail(error)
            return ToolResult.failure_result(
                tool_name=tool_name,
                error_message=error,
                error_code=-32601,  # Method not found
            )

        # Validate arguments
        validation_errors = await tool.validate_arguments(arguments)
        if validation_errors:
            error = f"Validation failed: {', '.join(validation_errors)}"
            record.fail(error)
            return ToolResult.failure_result(
                tool_name=tool_name,
                error_message=error,
                error_code=-32602,  # Invalid params
            )

        # Execute with concurrency control
        timeout_seconds = timeout or self._default_timeout

        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    tool.execute(arguments, context),
                    timeout=timeout_seconds,
                )
                record.complete(result)
                return result

        except asyncio.TimeoutError:
            error = f"Tool '{tool_name}' execution timed out after {timeout_seconds}s"
            record.fail(error)
            return ToolResult.failure_result(
                tool_name=tool_name,
                error_message=error,
                error_code=-32006,  # Timeout error
            )

        except Exception as e:
            error = f"Tool '{tool_name}' execution failed: {str(e)}"
            record.fail(error)
            return ToolResult.failure_result(
                tool_name=tool_name,
                error_message=error,
                error_code=-32603,  # Internal error
            )

    async def dispatch_batch(
        self,
        calls: List[Dict[str, Any]],
        context: Optional[ToolExecutionContext] = None,
    ) -> List[ToolResult]:
        """Dispatch multiple tool calls in parallel.

        Args:
            calls: List of {tool_name, arguments} dicts
            context: Execution context

        Returns:
            List of ToolResults in same order as calls
        """
        tasks = [
            self.dispatch(
                call["tool_name"],
                call.get("arguments", {}),
                context,
            )
            for call in calls
        ]
        return await asyncio.gather(*tasks)

    def _add_to_history(self, record: ToolCallRecord) -> None:
        """Add a call record to history."""
        self._call_history.append(record)
        # Trim history if needed
        if len(self._call_history) > self._max_history:
            self._call_history = self._call_history[-self._max_history:]

    def get_call_history(
        self,
        tool_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get call history.

        Args:
            tool_name: Filter by tool name (optional)
            limit: Maximum records to return

        Returns:
            List of call records as dictionaries
        """
        history = self._call_history
        if tool_name:
            history = [r for r in history if r.tool_name == tool_name]
        return [r.to_dict() for r in history[-limit:]]

    def clear_history(self) -> None:
        """Clear call history."""
        self._call_history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get dispatcher statistics.

        Returns:
            Statistics dictionary
        """
        total_calls = len(self._call_history)
        successful = sum(
            1 for r in self._call_history
            if r.result and r.result.is_success()
        )
        failed = total_calls - successful

        # Calculate average duration
        durations = [
            r.duration_ms for r in self._call_history
            if r.duration_ms is not None
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "totalCalls": total_calls,
            "successfulCalls": successful,
            "failedCalls": failed,
            "averageDurationMs": avg_duration,
            "registeredTools": len(self.list_tools()),
            "maxConcurrentCalls": self._max_concurrent_calls,
        }


class McpService:
    """Main MCP service for tool management and execution.

    This is the primary entry point for MCP tool operations.

    Example:
        >>> service = McpService()
        >>> service.register_tool(QueryModelTool())
        >>> result = await service.call_tool("query_model", {"model": "users"})
    """

    def __init__(
        self,
        dispatcher: Optional[McpToolDispatcher] = None,
    ):
        """Initialize the service.

        Args:
            dispatcher: Tool dispatcher (creates new one if None)
        """
        self._dispatcher = dispatcher or McpToolDispatcher()

    def register_tool(self, tool: BaseMcpTool) -> None:
        """Register a tool.

        Args:
            tool: Tool to register
        """
        self._dispatcher.register_tool(tool)

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool.

        Args:
            name: Tool name

        Returns:
            True if unregistered
        """
        return self._dispatcher.unregister_tool(name)

    def get_tool(self, name: str) -> Optional[BaseMcpTool]:
        """Get a registered tool.

        Args:
            name: Tool name

        Returns:
            Tool or None
        """
        return self._dispatcher.get_tool(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools.

        Returns:
            List of tool info dictionaries
        """
        tools = []
        for tool in self._dispatcher.list_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "category": tool.category.value,
                "parameters": tool.get_parameters(),
            })
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None,
    ) -> ToolResult:
        """Call a tool.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            context: Execution context

        Returns:
            ToolResult
        """
        return await self._dispatcher.dispatch(tool_name, arguments, context)

    async def call_tools_batch(
        self,
        calls: List[Dict[str, Any]],
        context: Optional[ToolExecutionContext] = None,
    ) -> List[ToolResult]:
        """Call multiple tools in parallel.

        Args:
            calls: List of {tool_name, arguments} dicts
            context: Execution context

        Returns:
            List of ToolResults
        """
        return await self._dispatcher.dispatch_batch(calls, context)

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return self._dispatcher.get_stats()

    def get_call_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get call history.

        Args:
            limit: Maximum records

        Returns:
            List of call records
        """
        return self._dispatcher.get_call_history(limit=limit)

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Export tools in OpenAI function format.

        Returns:
            List of OpenAI tool definitions
        """
        return self._dispatcher._registry.to_openai_tools()


__all__ = [
    "ToolCallRecord",
    "McpToolDispatcher",
    "McpService",
]