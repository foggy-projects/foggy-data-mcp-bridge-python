"""Tool call schema definitions."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ToolCallStatus(str, Enum):
    """Tool call status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolCallRequest(BaseModel):
    """Tool call request."""

    # Tool identification
    tool_name: str = Field(..., description="Name of the tool to call")
    tool_version: Optional[str] = Field(default=None, description="Tool version")

    # Parameters
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")

    # Execution options
    timeout_seconds: Optional[int] = Field(default=None, description="Execution timeout")
    async_execution: bool = Field(default=False, description="Execute asynchronously")

    # Context
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")

    model_config = {"extra": "allow"}

    def get_argument(self, name: str, default: Any = None) -> Any:
        """Get an argument value by name."""
        return self.arguments.get(name, default)


class ToolCallResult(BaseModel):
    """Tool call result."""

    # Identification
    call_id: Optional[str] = Field(default=None, description="Call ID")
    tool_name: str = Field(..., description="Tool that was called")

    # Status
    status: ToolCallStatus = Field(default=ToolCallStatus.SUCCESS, description="Call status")

    # Result
    result: Optional[Any] = Field(default=None, description="Tool result")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    error_code: Optional[int] = Field(default=None, description="Error code if failed")

    # Metadata
    duration_ms: Optional[float] = Field(default=None, description="Execution duration")
    timestamp: datetime = Field(default_factory=datetime.now, description="Result timestamp")

    # Artifacts (files, charts, etc.)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Generated artifacts")

    model_config = {"extra": "allow"}

    @classmethod
    def success_result(cls, tool_name: str, result: Any, duration_ms: Optional[float] = None) -> "ToolCallResult":
        """Create a successful result."""
        return cls(
            tool_name=tool_name,
            status=ToolCallStatus.SUCCESS,
            result=result,
            duration_ms=duration_ms
        )

    @classmethod
    def failure_result(cls, tool_name: str, error_message: str, error_code: Optional[int] = None) -> "ToolCallResult":
        """Create a failure result."""
        return cls(
            tool_name=tool_name,
            status=ToolCallStatus.FAILED,
            error_message=error_message,
            error_code=error_code
        )

    @classmethod
    def timeout_result(cls, tool_name: str) -> "ToolCallResult":
        """Create a timeout result."""
        return cls(
            tool_name=tool_name,
            status=ToolCallStatus.TIMEOUT,
            error_message="Tool execution timed out"
        )

    def is_success(self) -> bool:
        """Check if result is successful."""
        return self.status == ToolCallStatus.SUCCESS


class ToolDefinition(BaseModel):
    """Tool definition for registration."""

    # Identity
    name: str = Field(..., description="Tool name (unique identifier)")
    display_name: Optional[str] = Field(default=None, description="Display name")
    description: str = Field(..., description="Tool description")
    version: str = Field(default="1.0.0", description="Tool version")

    # Category
    category: str = Field(default="general", description="Tool category")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering")

    # Parameters
    parameters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Parameter definitions"
    )

    # Return type
    return_type: str = Field(default="object", description="Return type")
    return_description: Optional[str] = Field(default=None, description="Return description")

    # Access control
    required_roles: List[str] = Field(default_factory=list, description="Required roles")
    allowed_user_types: List[str] = Field(default_factory=list, description="Allowed user types")

    # Execution settings
    timeout_seconds: int = Field(default=60, description="Default timeout")
    supports_pagination: bool = Field(default=False, description="Supports pagination")
    supports_async: bool = Field(default=False, description="Supports async execution")

    # Examples
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Usage examples")

    model_config = {"extra": "allow"}

    def to_openai_tool(self) -> Dict[str, Any]:
        """Convert to OpenAI tool format."""
        properties = {}
        required = []

        for param in self.parameters:
            name = param.get("name", "")
            properties[name] = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
            }
            if param.get("enum"):
                properties[name]["enum"] = param.get("enum")
            if param.get("required", False):
                required.append(name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }