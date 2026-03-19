"""Control flow expressions (block, if, for, while)."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor


class ExportExpression(Expression):
    """Export expression for exporting variables/functions.

    Tracks which variables should be exported from the module.
    """

    name: Optional[str] = Field(default=None, description="Name of exported item")
    value: Optional[Expression] = Field(default=None, description="Value to export")
    names: Optional[List[str]] = Field(default=None, description="List of names to export from context")
    is_default: bool = Field(default=False, description="Whether this is a default export")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate and register export.

        Returns the value and also registers it in __exports__ in context.
        """
        # Ensure __exports__ exists
        if "__exports__" not in context:
            context["__exports__"] = {}

        if self.is_default:
            # Default export
            if self.value:
                value = self.value.evaluate(context)
                context["__exports__"]["default"] = value
                return value
        elif self.name and self.value:
            # Named export with value: export var x = 1
            value = self.value.evaluate(context)
            context["__exports__"][self.name] = value
            # Also set in regular context
            context[self.name] = value
            return value
        elif self.names:
            # Export list: export {a, b, c}
            for name in self.names:
                if name in context:
                    context["__exports__"][name] = context[name]
            return None
        elif self.name:
            # Export existing variable: export var x (x already declared)
            if self.name in context:
                context["__exports__"][self.name] = context[self.name]
            return context.get(self.name)

        return None

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_export(self)

    def __repr__(self) -> str:
        if self.is_default:
            return f"export default {self.value}"
        if self.names:
            return f"export {{{', '.join(self.names)}}}"
        return f"export {self.name}"


class ImportExpression(Expression):
    """Import expression for importing from modules.

    Handles various import patterns:
    - import {a, b} from 'module'
    - import X from 'module'
    - import * as name from 'module'
    """

    module: str = Field(..., description="Module path to import from")
    names: Optional[List[tuple]] = Field(default=None, description="List of (name, alias) tuples")
    default_name: Optional[str] = Field(default=None, description="Name for default import")
    namespace: Optional[str] = Field(default=None, description="Namespace for import * as name")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate import by loading module and binding imports.

        This requires a module loader to be available in context.
        """
        # Get the module loader
        loader = context.get("__module_loader__")
        if not loader:
            # If no loader, just return None (simplified behavior)
            return None

        # Load the module and get its exports
        exports = loader.load_module(self.module, context)

        if self.namespace:
            # import * as name from 'module'
            # Bind all exports to the namespace
            ns = {}
            for name, value in exports.items():
                if name != "default":
                    ns[name] = value
            context[self.namespace] = ns
            return ns

        if self.default_name:
            # import X from 'module'
            default_value = exports.get("default")
            context[self.default_name] = default_value
            return default_value

        if self.names:
            # import {a, b} from 'module'
            for name, alias in self.names:
                actual_name = alias or name
                if name in exports:
                    context[actual_name] = exports[name]

        return None

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_import(self)

    def __repr__(self) -> str:
        if self.namespace:
            return f"import * as {self.namespace} from '{self.module}'"
        if self.default_name:
            return f"import {self.default_name} from '{self.module}'"
        if self.names:
            items = ", ".join(f"{n}" + (f" as {a}" if a else "") for n, a in self.names)
            return f"import {{{items}}} from '{self.module}'"
        return f"import from '{self.module}'"


class BlockExpression(Expression):
    """Block expression (sequence of statements)."""

    statements: List[Expression] = Field(default_factory=list, description="Statements")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate all statements and return last value."""
        result = None
        for stmt in self.statements:
            result = stmt.evaluate(context)
        return result

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_block(self)

    def add_statement(self, stmt: Expression) -> "BlockExpression":
        """Add a statement to the block.

        Args:
            stmt: Statement to add

        Returns:
            Self for chaining
        """
        self.statements.append(stmt)
        return self

    def __repr__(self) -> str:
        return f"Block({len(self.statements)} statements)"


class IfExpression(Expression):
    """If-else expression."""

    condition: Expression = Field(..., description="Condition")
    then_branch: Expression = Field(..., description="Then branch")
    else_branch: Optional[Expression] = Field(default=None, description="Else branch")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate condition and execute appropriate branch."""
        cond_val = self.condition.evaluate(context)

        if self._to_bool(cond_val):
            return self.then_branch.evaluate(context)
        elif self.else_branch:
            return self.else_branch.evaluate(context)
        return None

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_if(self)

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True

    def __repr__(self) -> str:
        else_part = f" else {self.else_branch}" if self.else_branch else ""
        return f"if ({self.condition}) {self.then_branch}{else_part}"


class ForExpression(Expression):
    """For loop expression."""

    # For-each style: for (item in array)
    variable: Optional[str] = Field(default=None, description="Loop variable name")
    iterable: Optional[Expression] = Field(default=None, description="Iterable expression")

    # For-in vs for-of: for-in iterates over indices/keys, for-of iterates over values
    is_for_in: bool = Field(default=False, description="True if this is a for-in loop (iterates over indices/keys)")

    # C-style: for (init; condition; update)
    init: Optional[Expression] = Field(default=None, description="Init expression")
    condition: Optional[Expression] = Field(default=None, description="Condition expression")
    update: Optional[Expression] = Field(default=None, description="Update expression")

    # Body
    body: Expression = Field(..., description="Loop body")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Execute the for loop."""
        result = None

        if self.variable and self.iterable:
            # For-each style
            iterable_val = self.iterable.evaluate(context)
            if isinstance(iterable_val, (list, tuple)):
                if self.is_for_in:
                    # for-in: iterate over indices
                    for i in range(len(iterable_val)):
                        context[self.variable] = i
                        result = self.body.evaluate(context)
                else:
                    # for-of: iterate over values
                    for item in iterable_val:
                        context[self.variable] = item
                        result = self.body.evaluate(context)
            elif isinstance(iterable_val, dict):
                # Both for-in and for-of iterate over keys for dicts
                for key in iterable_val:
                    context[self.variable] = key
                    result = self.body.evaluate(context)
            elif isinstance(iterable_val, str):
                if self.is_for_in:
                    # for-in: iterate over indices
                    for i in range(len(iterable_val)):
                        context[self.variable] = i
                        result = self.body.evaluate(context)
                else:
                    # for-of: iterate over characters
                    for char in iterable_val:
                        context[self.variable] = char
                        result = self.body.evaluate(context)

        elif self.init and self.condition:
            # C-style for loop
            local_context = context.copy()
            self.init.evaluate(local_context)

            while self._to_bool(self.condition.evaluate(local_context)):
                result = self.body.evaluate(local_context)
                if self.update:
                    self.update.evaluate(local_context)

        return result

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_for(self)

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return True

    def __repr__(self) -> str:
        if self.variable and self.iterable:
            return f"for ({self.variable} in {self.iterable}) {self.body}"
        return f"for ({self.init}; {self.condition}; {self.update}) {self.body}"


class WhileExpression(Expression):
    """While loop expression."""

    condition: Expression = Field(..., description="Loop condition")
    body: Expression = Field(..., description="Loop body")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Execute the while loop."""
        result = None

        while self._to_bool(self.condition.evaluate(context)):
            result = self.body.evaluate(context)

        return result

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_while(self)

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return True

    def __repr__(self) -> str:
        return f"while ({self.condition}) {self.body}"


class BreakExpression(Expression):
    """Break statement for loops."""

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Raise break exception."""
        raise BreakException()

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_break(self)

    def __repr__(self) -> str:
        return "break"


class ContinueExpression(Expression):
    """Continue statement for loops."""

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Raise continue exception."""
        raise ContinueException()

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_continue(self)

    def __repr__(self) -> str:
        return "continue"


class ReturnExpression(Expression):
    """Return statement for functions."""

    value: Optional[Expression] = Field(default=None, description="Return value")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Raise return exception with value."""
        val = self.value.evaluate(context) if self.value else None
        raise ReturnException(val)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_return(self)

    def __repr__(self) -> str:
        val_part = f" {self.value}" if self.value else ""
        return f"return{val_part}"


class BreakException(Exception):
    """Exception for break statement."""
    pass


class ContinueException(Exception):
    """Exception for continue statement."""
    pass


class ReturnException(Exception):
    """Exception for return statement."""

    def __init__(self, value: Any = None):
        super().__init__()
        self.value = value


class SwitchExpression(Expression):
    """Switch statement expression.

    Transforms to if-else chain internally but catches break statements.
    """

    discriminant: Expression = Field(..., description="Value to switch on")
    cases: List[tuple] = Field(default_factory=list, description="List of (test, body) tuples")
    default_body: Optional[Expression] = Field(default=None, description="Default case body")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate switch statement."""
        disc_value = self.discriminant.evaluate(context)

        # Try each case in order
        for test, body in self.cases:
            test_value = test.evaluate(context)
            if self._equals(disc_value, test_value):
                try:
                    return body.evaluate(context)
                except BreakException:
                    return None

        # Default case
        if self.default_body:
            try:
                return self.default_body.evaluate(context)
            except BreakException:
                return None

        return None

    def _equals(self, a: Any, b: Any) -> bool:
        """Check equality with type coercion."""
        if type(a) == type(b):
            return a == b
        # Try numeric comparison
        try:
            return float(a) == float(b)
        except (TypeError, ValueError):
            pass
        # Try string comparison
        return str(a) == str(b)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_switch(self)

    def __repr__(self) -> str:
        return f"switch ({self.discriminant}) {{ ... }}"


class ThrowException(Exception):
    """Exception raised by throw statement."""

    def __init__(self, value: Any = None):
        super().__init__()
        self.value = value


class ThrowExpression(Expression):
    """Throw expression for throwing exceptions."""

    value: Expression = Field(..., description="Value to throw")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate and throw exception."""
        val = self.value.evaluate(context)
        raise ThrowException(val)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_throw(self)

    def __repr__(self) -> str:
        return f"throw {self.value}"


class TryCatchExpression(Expression):
    """Try-catch-finally expression.

    Handles exception catching with optional catch variable and finally block.
    """

    try_body: Expression = Field(..., description="Try block body")
    catch_body: Optional[Expression] = Field(default=None, description="Catch block body")
    catch_var: Optional[str] = Field(default=None, description="Variable name for caught exception")
    finally_body: Optional[Expression] = Field(default=None, description="Finally block body")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate try-catch-finally."""
        result = None

        try:
            result = self.try_body.evaluate(context)
        except ThrowException as e:
            # Handle user-thrown exceptions
            if self.catch_body:
                # Save old value of catch variable if it exists
                old_value = context.get(self.catch_var) if self.catch_var else None

                # Set catch variable to thrown value
                if self.catch_var:
                    context[self.catch_var] = e.value

                try:
                    result = self.catch_body.evaluate(context)
                finally:
                    # Restore old value
                    if self.catch_var:
                        if old_value is None:
                            context.pop(self.catch_var, None)
                        else:
                            context[self.catch_var] = old_value
            else:
                # No catch block, re-raise after finally
                raise
        except Exception as e:
            # Handle other exceptions (runtime errors)
            if self.catch_body:
                # Save old value of catch variable if it exists
                old_value = context.get(self.catch_var) if self.catch_var else None

                # Set catch variable to exception
                if self.catch_var:
                    context[self.catch_var] = e

                try:
                    result = self.catch_body.evaluate(context)
                finally:
                    # Restore old value
                    if self.catch_var:
                        if old_value is None:
                            context.pop(self.catch_var, None)
                        else:
                            context[self.catch_var] = old_value
            else:
                # No catch block, execute finally and re-raise
                if self.finally_body:
                    self.finally_body.evaluate(context)
                raise
        finally:
            # Always execute finally block
            if self.finally_body:
                self.finally_body.evaluate(context)

        return result

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_try_catch(self)

    def __repr__(self) -> str:
        return f"try {{ ... }} catch ({self.catch_var}) {{ ... }}"


__all__ = [
    "BlockExpression",
    "IfExpression",
    "ForExpression",
    "WhileExpression",
    "BreakExpression",
    "ContinueExpression",
    "ReturnExpression",
    "BreakException",
    "ContinueException",
    "ReturnException",
    "ExportExpression",
    "ImportExpression",
    "SwitchExpression",
    "ThrowException",
    "ThrowExpression",
    "TryCatchExpression",
]