"""Base MCP Tool implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, ClassVar
from pydantic import BaseModel, Field

from foggy.mcp_spi.tool import McpTool, ToolCategory, ToolResult, ToolMetadata
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp.schema.tool import ToolDefinition


class BaseMcpTool(McpTool, ABC):
    """Base class for MCP tools with common functionality."""

    # Class-level metadata (override in subclasses)
    tool_name: ClassVar[str] = "base_tool"
    tool_description: ClassVar[str] = "Base tool class"
    tool_category: ClassVar[ToolCategory] = ToolCategory.GENERAL
    tool_tags: ClassVar[List[str]] = []

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the tool with optional configuration."""
        self._config = config or {}
        self._initialized = False

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self.tool_name

    @property
    def description(self) -> str:
        """Get the tool description."""
        return self.tool_description

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return self.tool_category

    @property
    def metadata(self) -> ToolMetadata:
        """Get tool metadata."""
        return ToolMetadata(
            name=self.tool_name,
            description=self.tool_description,
            category=self.tool_category,
            version=self.get_version(),
            parameters=self.get_parameters(),
            tags=self.tool_tags,
        )

    def get_version(self) -> str:
        """Get tool version."""
        return "1.0.0"

    def get_parameters(self) -> List[Dict[str, Any]]:
        """Get parameter definitions. Override in subclasses."""
        return []

    def get_tool_definition(self) -> ToolDefinition:
        """Get the tool definition for registration."""
        return ToolDefinition(
            name=self.tool_name,
            display_name=self.tool_name.replace("_", " ").title(),
            description=self.tool_description,
            category=self.tool_category.value,
            tags=self.tool_tags,
            parameters=self.get_parameters(),
            timeout_seconds=60,
        )

    async def initialize(self) -> None:
        """Initialize the tool. Override for custom initialization."""
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the tool. Override for custom cleanup."""
        self._initialized = False

    def is_initialized(self) -> bool:
        """Check if the tool is initialized."""
        return self._initialized

    @abstractmethod
    async def execute(
        self,
        arguments: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolResult:
        """Execute the tool with given arguments."""
        pass

    async def validate_arguments(self, arguments: Dict[str, Any]) -> List[str]:
        """Validate tool arguments and return list of errors."""
        errors = []
        params = self.get_parameters()

        for param in params:
            name = param.get("name")
            required = param.get("required", False)

            if required and name not in arguments:
                errors.append(f"Required parameter '{name}' is missing")

        return errors

    def _success_result(self, data: Any, message: Optional[str] = None) -> ToolResult:
        """Create a successful tool result."""
        return ToolResult.success_result(
            tool_name=self.tool_name,
            data=data,
            message=message
        )

    def _error_result(self, error_message: str, error_code: Optional[int] = None) -> ToolResult:
        """Create an error tool result."""
        return ToolResult.failure_result(
            tool_name=self.tool_name,
            error_message=error_message,
            error_code=error_code
        )


class ToolRegistry:
    """Registry for MCP tools."""

    def __init__(self):
        """Initialize an empty registry."""
        self._tools: Dict[str, BaseMcpTool] = {}
        self._by_category: Dict[ToolCategory, List[str]] = {}

    def register(self, tool: BaseMcpTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

        category = tool.category
        if category not in self._by_category:
            self._by_category[category] = []
        self._by_category[category].append(tool.name)

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            tool = self._tools[name]
            category = tool.category
            if category in self._by_category and name in self._by_category[category]:
                self._by_category[category].remove(name)
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[BaseMcpTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseMcpTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> List[BaseMcpTool]:
        """List tools by category."""
        names = self._by_category.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions."""
        return [t.get_tool_definition() for t in self._tools.values()]

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Export tools in OpenAI format."""
        return [t.get_tool_definition().to_openai_tool() for t in self._tools.values()]