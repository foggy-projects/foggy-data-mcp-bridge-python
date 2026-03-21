"""Expression evaluator for FSScript.

The evaluator executes expression trees and returns results.
"""

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from foggy.fsscript.module_loader import ModuleLoader

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor
from foggy.fsscript.expressions.literals import (
    LiteralExpression,
    ArrayExpression,
    ObjectExpression,
    TemplateLiteralExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryExpression,
    UnaryExpression,
    TernaryExpression,
)
from foggy.fsscript.expressions.variables import (
    VariableExpression,
    MemberAccessExpression,
    IndexAccessExpression,
    AssignmentExpression,
)
from foggy.fsscript.expressions.functions import (
    FunctionCallExpression,
    MethodCallExpression,
    FunctionDefinitionExpression,
)
from foggy.fsscript.expressions.control_flow import (
    BlockExpression,
    IfExpression,
    ForExpression,
    WhileExpression,
    BreakExpression,
    ContinueExpression,
    ReturnExpression,
    BreakException,
    ContinueException,
    ReturnException,
    SwitchExpression,
)
from foggy.fsscript.globals.array import ArrayGlobal
from foggy.fsscript.globals.console import ConsoleGlobal
from foggy.fsscript.globals.json_global import JsonGlobal
from foggy.fsscript.scope import ScopeChain


class ExpressionEvaluator(ExpressionVisitor):
    """Evaluates expression trees.

    Implements the Visitor pattern to evaluate each expression type.
    """

    def __init__(
        self,
        context: Optional[Dict[str, Any]] = None,
        module_loader: Optional["ModuleLoader"] = None,
        bean_registry: Optional["BeanRegistry"] = None,
    ):
        """Initialize evaluator.

        Args:
            context: Initial context with variables and functions
            module_loader: Module loader for import statements
            bean_registry: Bean registry for ``import '@beanName'`` support
        """
        if isinstance(context, ScopeChain):
            self._context = context
        else:
            self._context = ScopeChain([context or {}])
        self._module_loader = module_loader
        self._setup_builtins()

        # Wire up bean registry as a BeanModuleLoader in the loader chain
        if bean_registry:
            from foggy.fsscript.bean_registry import BeanModuleLoader
            from foggy.fsscript.module_loader import ChainedModuleLoader
            bean_loader = BeanModuleLoader(bean_registry)
            if module_loader:
                module_loader = ChainedModuleLoader(bean_loader, module_loader)
            else:
                module_loader = bean_loader
            self._module_loader = module_loader
            self._context["__bean_registry__"] = bean_registry

        # Register module loader in context for ImportExpression
        if module_loader or self._module_loader:
            self._context["__module_loader__"] = self._module_loader or module_loader

    def _setup_builtins(self) -> None:
        """Set up built-in globals."""
        # Array functions (for Array.xxx style calls)
        array_global = ArrayGlobal()
        for name, func in array_global.get_functions().items():
            self._context[f"Array_{name}"] = func

        # Console (for Console.xxx style calls)
        console = ConsoleGlobal()
        for name, func in console.get_functions().items():
            self._context[f"Console_{name}"] = func

        # JSON object (for JSON.parse, JSON.stringify style calls)
        json_global = JsonGlobal()
        # Register as an object with methods
        self._context["JSON"] = json_global

        # Built-in functions
        self._context["parseInt"] = lambda x, base=10: int(x, base) if isinstance(x, str) else int(x)
        self._context["parseFloat"] = lambda x: float(x) if isinstance(x, str) else float(x)
        self._context["toString"] = lambda x: str(x)
        self._context["String"] = lambda x: str(x)
        self._context["Number"] = lambda x: float(x) if '.' in str(x) else int(x)
        self._context["Boolean"] = lambda x: bool(x)
        self._context["isNaN"] = lambda x: x != x  # NaN != NaN is True
        self._context["isFinite"] = lambda x: x != float('inf') and x != float('-inf') and x == x

        # Constructor types — used by `instanceof` operator
        self._context["Array"] = list
        self._context["Object"] = dict
        self._context["Function"] = type(lambda: None)

        # typeof built-in function (in addition to the operator)
        from foggy.fsscript.expressions.operators import fsscript_typeof
        self._context["typeof"] = fsscript_typeof

    @property
    def context(self) -> Dict[str, Any]:
        """Get the current context."""
        return self._context

    def evaluate(self, expression: Expression) -> Any:
        """Evaluate an expression.

        Args:
            expression: Expression to evaluate

        Returns:
            Evaluation result
        """
        return expression.accept(self)

    def evaluate_with_context(self, expression: Expression, context: Dict[str, Any]) -> Any:
        """Evaluate an expression with additional context.

        Args:
            expression: Expression to evaluate
            context: Additional context variables

        Returns:
            Evaluation result
        """
        # Save current context
        saved_context = self._context.copy()

        # Merge contexts
        self._context.update(context)

        try:
            return expression.accept(self)
        finally:
            # Restore context
            self._context = saved_context

    # Visitor methods

    def visit_literal(self, expr: LiteralExpression) -> Any:
        """Visit a literal expression."""
        return expr.value

    def visit_binary(self, expr: BinaryExpression) -> Any:
        """Visit a binary expression."""
        return expr.evaluate(self._context)

    def visit_unary(self, expr: UnaryExpression) -> Any:
        """Visit a unary expression."""
        return expr.evaluate(self._context)

    def visit_ternary(self, expr: TernaryExpression) -> Any:
        """Visit a ternary expression."""
        return expr.evaluate(self._context)

    def visit_variable(self, expr: VariableExpression) -> Any:
        """Visit a variable expression."""
        return self._context.get(expr.name)

    def visit_member_access(self, expr: MemberAccessExpression) -> Any:
        """Visit a member access expression."""
        return expr.evaluate(self._context)

    def visit_index_access(self, expr: IndexAccessExpression) -> Any:
        """Visit an index access expression."""
        return expr.evaluate(self._context)

    def visit_assignment(self, expr: AssignmentExpression) -> Any:
        """Visit an assignment expression."""
        return expr.evaluate(self._context)

    def visit_function_call(self, expr: FunctionCallExpression) -> Any:
        """Visit a function call expression."""
        return expr.evaluate(self._context)

    def visit_method_call(self, expr: MethodCallExpression) -> Any:
        """Visit a method call expression."""
        return expr.evaluate(self._context)

    def visit_function_definition(self, expr: FunctionDefinitionExpression) -> Any:
        """Visit a function definition expression."""
        return expr.evaluate(self._context)

    def visit_block(self, expr: BlockExpression) -> Any:
        """Visit a block expression."""
        result = None
        for stmt in expr.statements:
            result = stmt.accept(self)
        return result

    def visit_if(self, expr: IfExpression) -> Any:
        """Visit an if expression."""
        cond_val = expr.condition.accept(self)
        if self._to_bool(cond_val):
            return expr.then_branch.accept(self)
        elif expr.else_branch:
            return expr.else_branch.accept(self)
        return None

    def visit_for(self, expr: ForExpression) -> Any:
        """Visit a for expression with per-iteration let scoping."""
        result = None

        if expr.variable and expr.iterable:
            # For-each style
            iterable_val = expr.iterable.accept(self)
            items = self._for_iteration_items(expr, iterable_val)
            for item in items:
                # Per-iteration scope for let variables
                if isinstance(self._context, ScopeChain):
                    self._context.push_scope()
                    self._context.declare(expr.variable, item)
                else:
                    self._context[expr.variable] = item
                try:
                    result = expr.body.accept(self)
                except BreakException:
                    break
                except ContinueException:
                    continue
                finally:
                    if isinstance(self._context, ScopeChain):
                        self._context.pop_scope()

        elif expr.init and expr.condition:
            # C-style for loop
            # Check if init is a let/const declaration (is_declaration flag)
            is_let = self._is_let_init(expr.init)

            # Push a scope for the for-loop's init variable
            if is_let and isinstance(self._context, ScopeChain):
                self._context.push_scope()

            expr.init.accept(self)
            var_name = self._get_init_var_name(expr.init)

            while self._to_bool(expr.condition.accept(self)):
                if is_let and var_name and isinstance(self._context, ScopeChain):
                    # Per-iteration scope: snapshot current loop var value
                    current_val = self._context.get(var_name)
                    self._context.push_scope()
                    self._context.declare(var_name, current_val)

                try:
                    result = expr.body.accept(self)
                except BreakException:
                    if is_let and var_name and isinstance(self._context, ScopeChain):
                        self._context.pop_scope()
                    break
                except ContinueException:
                    pass

                if is_let and var_name and isinstance(self._context, ScopeChain):
                    self._context.pop_scope()

                if expr.update:
                    expr.update.accept(self)

            if is_let and isinstance(self._context, ScopeChain):
                self._context.pop_scope()

        return result

    @staticmethod
    def _for_iteration_items(expr, iterable_val):
        """Get items for for-each iteration."""
        if isinstance(iterable_val, (list, tuple)):
            if expr.is_for_in:
                return list(range(len(iterable_val)))
            return list(iterable_val)
        elif isinstance(iterable_val, dict):
            return list(iterable_val.keys())
        elif isinstance(iterable_val, str):
            if expr.is_for_in:
                return list(range(len(iterable_val)))
            return list(iterable_val)
        return []

    @staticmethod
    def _is_let_init(init_expr) -> bool:
        """Check if for-loop init is a let/const (block-scoped) declaration."""
        from foggy.fsscript.expressions.variables import AssignmentExpression
        if isinstance(init_expr, AssignmentExpression):
            return init_expr.is_block_scoped
        return False

    @staticmethod
    def _get_init_var_name(init_expr) -> str:
        """Extract variable name from for-loop init expression."""
        from foggy.fsscript.expressions.variables import AssignmentExpression, VariableExpression
        if isinstance(init_expr, AssignmentExpression) and isinstance(init_expr.target, VariableExpression):
            return init_expr.target.name
        return None

        return result

    def visit_while(self, expr: WhileExpression) -> Any:
        """Visit a while expression."""
        result = None
        while self._to_bool(expr.condition.accept(self)):
            try:
                result = expr.body.accept(self)
            except BreakException:
                break
            except ContinueException:
                continue
        return result

    def visit_spread(self, expr: "SpreadExpression") -> Any:
        """Visit a spread expression."""
        from foggy.fsscript.expressions.literals import SpreadExpression
        return expr.expression.accept(self)

    def visit_break(self, expr: BreakExpression) -> Any:
        """Visit a break expression."""
        raise BreakException()

    def visit_continue(self, expr: ContinueExpression) -> Any:
        """Visit a continue expression."""
        raise ContinueException()

    def visit_return(self, expr: ReturnExpression) -> Any:
        """Visit a return expression."""
        val = expr.value.accept(self) if expr.value else None
        raise ReturnException(val)

    def visit_array(self, expr: ArrayExpression) -> Any:
        """Visit an array expression."""
        from foggy.fsscript.expressions.literals import SpreadExpression
        result = []
        for elem in expr.elements:
            if isinstance(elem, SpreadExpression):
                spread_val = elem.expression.accept(self)
                if isinstance(spread_val, list):
                    result.extend(spread_val)
                elif spread_val is not None:
                    result.append(spread_val)
            else:
                result.append(elem.accept(self))
        return result

    def visit_object(self, expr: ObjectExpression) -> Any:
        """Visit an object expression."""
        return {
            key: value.accept(self)
            for key, value in expr.properties.items()
        }

    def visit_update(self, expr: "UpdateExpression") -> Any:
        """Visit an update expression (increment/decrement)."""
        return expr.evaluate(self._context)

    def visit_export(self, expr: "ExportExpression") -> Any:
        """Visit an export expression."""
        return expr.evaluate(self._context)

    def visit_import(self, expr: "ImportExpression") -> Any:
        """Visit an import expression."""
        return expr.evaluate(self._context)

    def visit_switch(self, expr: "SwitchExpression") -> Any:
        """Visit a switch expression."""
        return expr.evaluate(self._context)

    def visit_throw(self, expr: "ThrowExpression") -> Any:
        """Visit a throw expression."""
        return expr.evaluate(self._context)

    def visit_try_catch(self, expr: "TryCatchExpression") -> Any:
        """Visit a try-catch-finally expression."""
        return expr.evaluate(self._context)

    def visit_template_literal(self, expr: "TemplateLiteralExpression") -> Any:
        """Visit a template literal expression."""
        return expr.evaluate(self._context)

    def get_exports(self) -> Dict[str, Any]:
        """Get the exported values from the context.

        Returns:
            Dictionary of exported names to values
        """
        return self._context.get("__exports__", {})

    def _to_bool(self, value: Any) -> bool:
        """Convert value to boolean."""
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

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in context.

        Args:
            name: Variable name
            value: Variable value
        """
        self._context[name] = value

    def get_variable(self, name: str) -> Any:
        """Get a variable from context.

        Args:
            name: Variable name

        Returns:
            Variable value or None
        """
        return self._context.get(name)

    def define_function(self, name: str, func: Callable) -> None:
        """Define a function in context.

        Args:
            name: Function name
            func: Callable function
        """
        self._context[name] = func

    def set_module_loader(self, loader: "ModuleLoader") -> None:
        """Set the module loader for import statements.

        Args:
            loader: Module loader instance
        """
        self._module_loader = loader
        self._context["__module_loader__"] = loader

    def get_module_loader(self) -> Optional["ModuleLoader"]:
        """Get the current module loader.

        Returns:
            Current module loader or None
        """
        return self._module_loader


class SimpleExpressionEvaluator:
    """Simple evaluator for basic expression evaluation.

    Provides a simpler interface for evaluating expressions without
    the full visitor machinery.
    """

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """Initialize evaluator.

        Args:
            context: Initial context
        """
        self._context = context or {}

    def evaluate(self, expression: Expression) -> Any:
        """Evaluate an expression.

        Args:
            expression: Expression to evaluate

        Returns:
            Evaluation result
        """
        return expression.evaluate(self._context)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable."""
        self._context[name] = value

    def get_variable(self, name: str) -> Any:
        """Get a variable."""
        return self._context.get(name)


__all__ = [
    "ExpressionEvaluator",
    "SimpleExpressionEvaluator",
]