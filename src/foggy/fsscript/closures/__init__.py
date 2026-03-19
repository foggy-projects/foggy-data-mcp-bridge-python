"""Closure system for FSScript.

Closures allow functions to capture and access variables from their
enclosing scope, enabling functional programming patterns.
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class ClosureContext(BaseModel):
    """Context for a closure, capturing variables from enclosing scope.

    A closure context stores the variable bindings that were in scope
    when the closure was created.
    """

    # Captured variables
    captured: Dict[str, Any] = Field(default_factory=dict, description="Captured variables")

    # Parent closure (for nested closures)
    parent: Optional["ClosureContext"] = Field(default=None, description="Parent closure")

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def get(self, name: str) -> Any:
        """Get a captured variable.

        Args:
            name: Variable name

        Returns:
            Variable value or None if not found
        """
        if name in self.captured:
            return self.captured[name]
        if self.parent:
            return self.parent.get(name)
        return None

    def set(self, name: str, value: Any) -> None:
        """Set a captured variable.

        Args:
            name: Variable name
            value: Variable value
        """
        self.captured[name] = value

    def has(self, name: str) -> bool:
        """Check if a variable is captured.

        Args:
            name: Variable name

        Returns:
            True if variable is captured
        """
        if name in self.captured:
            return True
        if self.parent:
            return self.parent.has(name)
        return False

    def capture(self, name: str, value: Any) -> None:
        """Capture a variable (shorthand for set).

        Args:
            name: Variable name
            value: Variable value
        """
        self.captured[name] = value

    def capture_all(self, variables: Dict[str, Any]) -> None:
        """Capture multiple variables.

        Args:
            variables: Dictionary of variables to capture
        """
        self.captured.update(variables)

    def get_all_captured(self) -> Dict[str, Any]:
        """Get all captured variables including from parent closures.

        Returns:
            Dictionary of all captured variables
        """
        result = {}
        if self.parent:
            result.update(self.parent.get_all_captured())
        result.update(self.captured)
        return result


class Closure(BaseModel):
    """Closure representing a function with its captured environment.

    A closure combines a function body with the closure context
    that captures variables from the enclosing scope.
    """

    # Function definition
    parameters: List[str] = Field(default_factory=list, description="Parameter names")
    body: Any = Field(..., description="Function body (Expression)")

    # Captured environment
    context: ClosureContext = Field(
        default_factory=ClosureContext, description="Closure context"
    )

    # Name (for named functions)
    name: Optional[str] = Field(default=None, description="Function name")

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def call(self, *args: Any) -> Any:
        """Call the closure with arguments.

        Args:
            *args: Arguments to pass

        Returns:
            Function result
        """
        # Create execution context with captured variables
        exec_context = self.context.get_all_captured()

        # Bind parameters
        for i, param in enumerate(self.parameters):
            exec_context[param] = args[i] if i < len(args) else None

        # Execute body (body should be an Expression)
        if callable(self.body):
            return self.body(exec_context)
        elif hasattr(self.body, "evaluate"):
            return self.body.evaluate(exec_context)
        else:
            return self.body

    def to_callable(self) -> Callable:
        """Convert to a Python callable.

        Returns:
            Callable function
        """
        return self.call

    def __call__(self, *args: Any) -> Any:
        """Allow calling the closure directly."""
        return self.call(*args)


class ClosureBuilder:
    """Builder for creating closures.

    Provides a fluent API for constructing closures step by step.
    """

    def __init__(self):
        """Initialize builder."""
        self._parameters: List[str] = []
        self._body: Any = None
        self._context: ClosureContext = ClosureContext()
        self._name: Optional[str] = None

    def with_parameter(self, name: str) -> "ClosureBuilder":
        """Add a parameter.

        Args:
            name: Parameter name

        Returns:
            Self for chaining
        """
        self._parameters.append(name)
        return self

    def with_parameters(self, *names: str) -> "ClosureBuilder":
        """Add multiple parameters.

        Args:
            *names: Parameter names

        Returns:
            Self for chaining
        """
        self._parameters.extend(names)
        return self

    def with_body(self, body: Any) -> "ClosureBuilder":
        """Set the function body.

        Args:
            body: Function body (Expression or callable)

        Returns:
            Self for chaining
        """
        self._body = body
        return self

    def capture(self, name: str, value: Any) -> "ClosureBuilder":
        """Capture a variable.

        Args:
            name: Variable name
            value: Variable value

        Returns:
            Self for chaining
        """
        self._context.capture(name, value)
        return self

    def capture_all(self, variables: Dict[str, Any]) -> "ClosureBuilder":
        """Capture multiple variables.

        Args:
            variables: Variables to capture

        Returns:
            Self for chaining
        """
        self._context.capture_all(variables)
        return self

    def with_name(self, name: str) -> "ClosureBuilder":
        """Set the function name.

        Args:
            name: Function name

        Returns:
            Self for chaining
        """
        self._name = name
        return self

    def build(self) -> Closure:
        """Build the closure.

        Returns:
            Built closure
        """
        return Closure(
            parameters=self._parameters,
            body=self._body,
            context=self._context,
            name=self._name,
        )


class ClosureRegistry:
    """Registry for closures.

    Provides storage and lookup for closures by name.
    """

    def __init__(self):
        """Initialize registry."""
        self._closures: Dict[str, Closure] = {}

    def register(self, closure: Closure) -> None:
        """Register a closure by name.

        Args:
            closure: Closure to register
        """
        if closure.name:
            self._closures[closure.name] = closure

    def get(self, name: str) -> Optional[Closure]:
        """Get a closure by name.

        Args:
            name: Closure name

        Returns:
            Closure or None if not found
        """
        return self._closures.get(name)

    def has(self, name: str) -> bool:
        """Check if a closure exists.

        Args:
            name: Closure name

        Returns:
            True if closure exists
        """
        return name in self._closures

    def remove(self, name: str) -> Optional[Closure]:
        """Remove a closure by name.

        Args:
            name: Closure name

        Returns:
            Removed closure or None
        """
        return self._closures.pop(name, None)

    def get_all_names(self) -> List[str]:
        """Get all registered closure names.

        Returns:
            List of closure names
        """
        return list(self._closures.keys())


__all__ = [
    "ClosureContext",
    "Closure",
    "ClosureBuilder",
    "ClosureRegistry",
]