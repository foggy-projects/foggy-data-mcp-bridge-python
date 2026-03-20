"""Function call and definition expressions."""

from typing import Any, Callable, Dict, List, Optional
from pydantic import Field

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor


class FunctionCallExpression(Expression):
    """Function call expression."""

    function: Expression = Field(..., description="Function expression")
    arguments: List[Expression] = Field(default_factory=list, description="Arguments")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate function call."""
        # Handle method calls (when function is a MemberAccessExpression)
        from foggy.fsscript.expressions.variables import MemberAccessExpression

        if isinstance(self.function, MemberAccessExpression):
            # This is a method call
            obj_val = self.function.obj.evaluate(context)
            method_name = self.function.member
            args = [arg.evaluate(context) for arg in self.arguments]

            if obj_val is None:
                raise RuntimeError(f"Cannot call method '{method_name}' on null")

            # Handle built-in methods for common types
            if isinstance(obj_val, str):
                return self._call_string_method(obj_val, method_name, args)
            elif isinstance(obj_val, list):
                return self._call_list_method(obj_val, method_name, args)
            elif isinstance(obj_val, dict):
                # First check if dict has a callable value at this key
                member_val = obj_val.get(method_name)
                if callable(member_val):
                    return member_val(*args)
                return self._call_dict_method(obj_val, method_name, args)

            # Try to get method from object
            method = getattr(obj_val, method_name, None)
            if callable(method):
                return method(*args)

            raise RuntimeError(f"Unknown method '{method_name}' on {type(obj_val).__name__}")

        # Regular function call
        func_val = self.function.evaluate(context)

        if func_val is None:
            raise RuntimeError(f"Cannot call null as function")

        # Evaluate arguments
        args = [arg.evaluate(context) for arg in self.arguments]

        if callable(func_val):
            return func_val(*args)
        elif isinstance(func_val, dict) and "__call__" in func_val:
            return func_val["__call__"](*args)
        else:
            raise RuntimeError(f"Cannot call {type(func_val).__name__} as function")

    def _call_string_method(self, obj: str, method: str, args: List[Any]) -> Any:
        """Call string method."""
        method = method.lower()
        if method == "length" or method == "len":
            return len(obj)
        elif method == "upper":
            return obj.upper()
        elif method == "lower":
            return obj.lower()
        elif method == "trim":
            return obj.strip()
        elif method == "split":
            sep = args[0] if args else None
            return obj.split(sep) if sep else obj.split()
        elif method == "substring":
            start = int(args[0]) if args else 0
            end = int(args[1]) if len(args) > 1 else len(obj)
            return obj[start:end]
        elif method == "replace":
            old = str(args[0]) if args else ""
            new = str(args[1]) if len(args) > 1 else ""
            return obj.replace(old, new)
        elif method == "contains":
            return str(args[0]) in obj if args else False
        elif method == "startswith":
            return obj.startswith(str(args[0])) if args else False
        elif method == "endswith":
            return obj.endswith(str(args[0])) if args else False
        else:
            raise RuntimeError(f"Unknown string method '{method}'")

    def _call_list_method(self, obj: list, method: str, args: List[Any]) -> Any:
        """Call list method."""
        method = method.lower()
        if method == "length" or method == "len" or method == "size":
            return len(obj)
        elif method == "push" or method == "append":
            obj.append(args[0] if args else None)
            return len(obj)
        elif method == "pop":
            return obj.pop() if obj else None
        elif method == "shift":
            return obj.pop(0) if obj else None
        elif method == "unshift":
            obj.insert(0, args[0] if args else None)
            return len(obj)
        elif method == "join":
            sep = str(args[0]) if args else ","
            # Format numbers without trailing .0
            def format_val(x):
                if isinstance(x, float) and x.is_integer():
                    return str(int(x))
                return str(x)
            return sep.join(format_val(x) for x in obj)
        elif method == "reverse":
            obj.reverse()
            return obj
        elif method == "sort":
            obj.sort()
            return obj
        elif method == "slice":
            start = int(args[0]) if args else 0
            end = int(args[1]) if len(args) > 1 else len(obj)
            return obj[start:end]
        elif method == "concat":
            return obj + (args[0] if args else [])
        elif method == "indexof":
            try:
                return obj.index(args[0]) if args else -1
            except ValueError:
                return -1
        elif method == "map":
            # Map with callback function
            callback = args[0] if args else None
            if callback is None:
                return obj
            return [callback(item) for item in obj]
        elif method == "filter":
            # Filter with callback function
            callback = args[0] if args else None
            if callback is None:
                return obj
            return [item for item in obj if callback(item)]
        elif method == "includes":
            # Check if item is in array
            return args[0] in obj if args else False
        elif method == "find":
            # Find first matching element
            callback = args[0] if args else None
            if callback is None:
                return None
            for item in obj:
                if callback(item):
                    return item
            return None
        elif method == "findindex":
            # Find index of first matching element
            callback = args[0] if args else None
            if callback is None:
                return -1
            for i, item in enumerate(obj):
                if callback(item):
                    return i
            return -1
        elif method == "reduce":
            # Reduce array to single value
            callback = args[0] if args else None
            initial = args[1] if len(args) > 1 else None
            if callback is None:
                return initial
            result = initial
            for item in obj:
                result = callback(result, item) if result is not None else item
            return result
        elif method == "every":
            # Check if all elements pass test
            callback = args[0] if args else None
            if callback is None:
                return True
            return all(callback(item) for item in obj)
        elif method == "some":
            # Check if any element passes test
            callback = args[0] if args else None
            if callback is None:
                return False
            return any(callback(item) for item in obj)
        elif method == "foreach":
            # forEach with callback function
            callback = args[0] if args else None
            if callback:
                for item in obj:
                    callback(item)
            return None
        elif method == "add":
            # Add item to array (alias for push, but returns array for chaining)
            obj.append(args[0] if args else None)
            return obj
        else:
            raise RuntimeError(f"Unknown list method '{method}'")

    def _call_dict_method(self, obj: dict, method: str, args: List[Any]) -> Any:
        """Call dict method."""
        method = method.lower()
        if method == "keys":
            return list(obj.keys())
        elif method == "values":
            return list(obj.values())
        elif method == "entries":
            return [[k, v] for k, v in obj.items()]
        elif method == "has" or method == "haskey":
            return args[0] in obj if args else False
        elif method == "get":
            return obj.get(args[0], args[1] if len(args) > 1 else None) if args else None
        elif method == "size" or method == "len" or method == "length":
            return len(obj)
        elif method == "remove":
            return obj.pop(args[0], None) if args else None
        elif method == "set":
            if len(args) >= 2:
                obj[args[0]] = args[1]
            return obj
        elif method == "delete":
            if args:
                obj.pop(args[0], None)
            return True
        else:
            raise RuntimeError(f"Unknown dict method '{method}'")

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_function_call(self)

    def __repr__(self) -> str:
        args_str = ", ".join(str(arg) for arg in self.arguments)
        return f"{self.function}({args_str})"


class MethodCallExpression(Expression):
    """Method call expression (obj.method(args))."""

    obj: Expression = Field(..., description="Object expression")
    method: str = Field(..., description="Method name")
    arguments: List[Expression] = Field(default_factory=list, description="Arguments")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate method call."""
        obj_val = self.obj.evaluate(context)

        if obj_val is None:
            raise RuntimeError(f"Cannot call method '{self.method}' on null")

        # Evaluate arguments
        args = [arg.evaluate(context) for arg in self.arguments]

        # Built-in methods for common types
        if isinstance(obj_val, str):
            return self._call_string_method(obj_val, args)
        elif isinstance(obj_val, list):
            return self._call_list_method(obj_val, args)
        elif isinstance(obj_val, dict):
            return self._call_dict_method(obj_val, args)

        # Try to get method from object
        method = getattr(obj_val, self.method, None)
        if callable(method):
            return method(*args)

        raise RuntimeError(f"Unknown method '{self.method}' on {type(obj_val).__name__}")

    def _call_string_method(self, obj: str, args: List[Any]) -> Any:
        """Call string method."""
        method = self.method.lower()
        if method == "length" or method == "len":
            return len(obj)
        elif method == "upper":
            return obj.upper()
        elif method == "lower":
            return obj.lower()
        elif method == "trim":
            return obj.strip()
        elif method == "split":
            sep = args[0] if args else None
            return obj.split(sep) if sep else obj.split()
        elif method == "substring":
            start = int(args[0]) if args else 0
            end = int(args[1]) if len(args) > 1 else len(obj)
            return obj[start:end]
        elif method == "replace":
            old = str(args[0]) if args else ""
            new = str(args[1]) if len(args) > 1 else ""
            return obj.replace(old, new)
        elif method == "contains":
            return str(args[0]) in obj if args else False
        elif method == "startswith":
            return obj.startswith(str(args[0])) if args else False
        elif method == "endswith":
            return obj.endswith(str(args[0])) if args else False
        else:
            raise RuntimeError(f"Unknown string method '{self.method}'")

    def _call_list_method(self, obj: list, args: List[Any]) -> Any:
        """Call list method."""
        method = self.method.lower()
        if method == "length" or method == "len" or method == "size":
            return len(obj)
        elif method == "push" or method == "append":
            obj.append(args[0] if args else None)
            return len(obj)
        elif method == "pop":
            return obj.pop() if obj else None
        elif method == "shift":
            return obj.pop(0) if obj else None
        elif method == "unshift":
            obj.insert(0, args[0] if args else None)
            return len(obj)
        elif method == "join":
            sep = str(args[0]) if args else ","
            # Format numbers without trailing .0
            def format_val(x):
                if isinstance(x, float) and x.is_integer():
                    return str(int(x))
                return str(x)
            return sep.join(format_val(x) for x in obj)
        elif method == "reverse":
            obj.reverse()
            return obj
        elif method == "sort":
            obj.sort()
            return obj
        elif method == "slice":
            start = int(args[0]) if args else 0
            end = int(args[1]) if len(args) > 1 else len(obj)
            return obj[start:end]
        elif method == "concat":
            return obj + (args[0] if args else [])
        elif method == "indexof":
            try:
                return obj.index(args[0]) if args else -1
            except ValueError:
                return -1
        elif method == "map":
            # Map with callback function
            callback = args[0] if args else None
            if callback is None:
                return obj
            return [callback(item) for item in obj]
        elif method == "filter":
            # Filter with callback function
            callback = args[0] if args else None
            if callback is None:
                return obj
            return [item for item in obj if callback(item)]
        elif method == "includes":
            # Check if item is in array
            return args[0] in obj if args else False
        elif method == "find":
            # Find first matching element
            callback = args[0] if args else None
            if callback is None:
                return None
            for item in obj:
                if callback(item):
                    return item
            return None
        elif method == "findindex":
            # Find index of first matching element
            callback = args[0] if args else None
            if callback is None:
                return -1
            for i, item in enumerate(obj):
                if callback(item):
                    return i
            return -1
        elif method == "reduce":
            # Reduce array to single value
            callback = args[0] if args else None
            initial = args[1] if len(args) > 1 else None
            if callback is None:
                return initial
            result = initial
            for item in obj:
                result = callback(result, item) if result is not None else item
            return result
        elif method == "every":
            # Check if all elements pass test
            callback = args[0] if args else None
            if callback is None:
                return True
            return all(callback(item) for item in obj)
        elif method == "some":
            # Check if any element passes test
            callback = args[0] if args else None
            if callback is None:
                return False
            return any(callback(item) for item in obj)
        elif method == "add":
            # Add item to array (alias for push, but returns array for chaining)
            obj.append(args[0] if args else None)
            return obj
        else:
            raise RuntimeError(f"Unknown list method '{self.method}'")

    def _call_dict_method(self, obj: dict, args: List[Any]) -> Any:
        """Call dict method."""
        method = self.method.lower()
        if method == "keys":
            return list(obj.keys())
        elif method == "values":
            return list(obj.values())
        elif method == "entries":
            return [[k, v] for k, v in obj.items()]
        elif method == "has" or method == "haskey":
            return args[0] in obj if args else False
        elif method == "get":
            return obj.get(args[0], args[1] if len(args) > 1 else None) if args else None
        elif method == "size" or method == "len" or method == "length":
            return len(obj)
        elif method == "remove":
            return obj.pop(args[0], None) if args else None
        else:
            raise RuntimeError(f"Unknown dict method '{self.method}'")

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_method_call(self)

    def __repr__(self) -> str:
        args_str = ", ".join(str(arg) for arg in self.arguments)
        return f"{self.obj}.{self.method}({args_str})"


class FunctionDefinitionExpression(Expression):
    """Function definition (lambda) expression."""

    parameters: List[str] = Field(default_factory=list, description="Parameter names")
    body: Expression = Field(..., description="Function body")
    name: Optional[str] = Field(default=None, description="Function name for named declarations")

    def evaluate(self, context: Dict[str, Any]) -> Callable:
        """Return a callable function with proper lexical closure.

        Captures the scope chain at definition time.  Each call gets the
        captured chain + a fresh local scope, matching JS/Java semantics.
        """
        from foggy.fsscript.scope import ScopeChain

        # 1. Capture scope chain at definition time
        if isinstance(context, ScopeChain):
            captured_scopes = context.snapshot_scopes()
        else:
            # Legacy path: wrap plain dict
            captured_scopes = [dict(context)]

        body_expr = self.body

        def func(*args):
            from foggy.fsscript.expressions.control_flow import ReturnException

            # 2. Create new scope chain: definition-time scopes + fresh local
            call_context = ScopeChain(captured_scopes)

            # 3. Bind parameters in local scope (shadowing, not polluting parent)
            for i, param in enumerate(self.parameters):
                call_context.declare(param, args[i] if i < len(args) else None)

            try:
                result = body_expr.evaluate(call_context)
            except ReturnException as e:
                result = e.value

            # 4. Propagate __exports__ back to the defining context
            _propagate_exports(call_context, context)
            return result

        # If named function, bind it to the context
        if self.name:
            context[self.name] = func

        return func

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_function_definition(self)

    def __repr__(self) -> str:
        params_str = ", ".join(self.parameters)
        if self.name:
            return f"function {self.name}({params_str}) => {self.body}"
        return f"({params_str}) => {self.body}"


def _propagate_exports(child_ctx, parent_ctx) -> None:
    """Copy __exports__ from child to parent context."""
    child_exports = child_ctx.get("__exports__")
    if child_exports:
        if "__exports__" not in parent_ctx:
            parent_ctx["__exports__"] = {}
        parent_exports = parent_ctx.get("__exports__")
        if isinstance(parent_exports, dict):
            parent_exports.update(child_exports)


__all__ = [
    "FunctionCallExpression",
    "MethodCallExpression",
    "FunctionDefinitionExpression",
]