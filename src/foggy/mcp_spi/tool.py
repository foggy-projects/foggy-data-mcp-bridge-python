"""MCP Tool interfaces and definitions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T")


class ToolCategory(Enum):
    """Tool category enumeration."""

    QUERY = "query"
    METADATA = "metadata"
    ADMIN = "admin"
    SYSTEM = "system"
    ANALYSIS = "analysis"
    EXPORT = "export"


@dataclass
class ToolMetadata:
    """Tool metadata definition."""

    name: str
    description: str
    category: ToolCategory = ToolCategory.QUERY
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    requires_auth: bool = True
    requires_admin: bool = False
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "requiresAuth": self.requires_auth,
            "requiresAdmin": self.requires_admin,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
        }


@dataclass
class ToolResult:
    """Tool execution result."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, metadata: Optional[Dict[str, Any]] = None) -> "ToolResult":
        """Create successful result."""
        return cls(
            success=True,
            data=data,
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        error: str,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create failed result."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "errorCode": self.error_code,
            "metadata": self.metadata,
        }


class McpTool(ABC):
    """Abstract base class for MCP tools.

    All tools must implement this interface to be registered
    with the MCP server.
    """

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Get tool metadata."""
        pass

    @abstractmethod
    async def execute(self, context: "ToolExecutionContext", **kwargs) -> ToolResult:
        """Execute the tool.

        Args:
            context: Execution context
            **kwargs: Tool arguments

        Returns:
            ToolResult containing success/failure and data
        """
        pass

    @property
    def name(self) -> str:
        """Get tool name."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """Get tool description."""
        return self.metadata.description

    def validate_input(self, **kwargs) -> Optional[str]:
        """Validate input arguments.

        Override this method to implement custom validation.

        Args:
            **kwargs: Tool arguments

        Returns:
            Error message if validation fails, None otherwise
        """
        return None

    def get_input_schema(self) -> Optional[Dict[str, Any]]:
        """Get JSON schema for input validation."""
        return self.metadata.input_schema

    def get_output_schema(self) -> Optional[Dict[str, Any]]:
        """Get JSON schema for output validation."""
        return self.metadata.output_schema