"""Unit tests for FSScript module."""

import pytest
from typing import Any, Dict
import io

from foggy.fsscript.bundle import (
    Bundle,
    BundleImpl,
    BundleResource,
    BundleState,
    SystemBundlesContext,
    FileBundleLoader,
    BundleLoadError,
)
from foggy.fsscript.conversion import (
    ConversionUtils,
    MapToObjectConverter,
    FsscriptConversionService,
)
from foggy.fsscript.expressions import (
    Expression,
    LiteralExpression,
    NullExpression,
    BooleanExpression,
    NumberExpression,
    StringExpression,
    ArrayExpression,
    ObjectExpression,
    BinaryExpression,
    UnaryExpression,
    TernaryExpression,
    BinaryOperator,
    UnaryOperator,
    VariableExpression,
    MemberAccessExpression,
    IndexAccessExpression,
    AssignmentExpression,
    FunctionCallExpression,
    MethodCallExpression,
    FunctionDefinitionExpression,
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
)
from foggy.fsscript.closures import (
    Closure,
    ClosureContext,
    ClosureBuilder,
    ClosureRegistry,
)
from foggy.fsscript.globals import ArrayGlobal, ConsoleGlobal, JsonGlobal
from foggy.fsscript.evaluator import ExpressionEvaluator, SimpleExpressionEvaluator


class TestBundleSystem:
    """Tests for bundle system."""

    def test_bundle_resource(self):
        """Test BundleResource creation."""
        resource = BundleResource(
            name="test.js",
            path="scripts/test.js",
            text_content="console.log('hello');"
        )
        assert resource.name == "test.js"
        assert resource.get_text() == "console.log('hello');"

    def test_bundle_impl(self):
        """Test BundleImpl creation and operations."""
        bundle = BundleImpl(bundle_id="test-bundle", name="Test Bundle", version="1.0.0")
        assert bundle.bundle_id == "test-bundle"
        assert bundle.name == "Test Bundle"
        assert bundle.state == BundleState.INSTALLED

    def test_bundle_lifecycle(self):
        """Test bundle start/stop lifecycle."""
        bundle = BundleImpl(bundle_id="test")
        assert bundle.state == BundleState.INSTALLED

        bundle.start()
        assert bundle.state == BundleState.ACTIVE

        bundle.stop()
        assert bundle.state == BundleState.RESOLVED

    def test_bundle_resources(self):
        """Test adding and getting resources from bundle."""
        bundle = BundleImpl(bundle_id="test")
        resource = BundleResource(name="config.json", path="config.json", text_content='{"key": "value"}')
        bundle.add_resource(resource)

        assert bundle.get_resource("config.json") is not None
        assert len(bundle.get_resources()) == 1

    def test_system_bundles_context(self):
        """Test SystemBundlesContext."""
        import foggy.fsscript as _fsscript_pkg
        from pathlib import Path
        fsscript_dir = str(Path(_fsscript_pkg.__file__).parent)

        ctx = SystemBundlesContext()
        bundle = ctx.install_bundle(fsscript_dir)

        assert bundle is not None
        assert bundle.bundle_id in ctx.bundles


class TestConversionUtils:
    """Tests for conversion utilities."""

    def test_to_string(self):
        """Test conversion to string."""
        assert ConversionUtils.to_string(None) == ""
        assert ConversionUtils.to_string(True) == "true"
        assert ConversionUtils.to_string(False) == "false"
        assert ConversionUtils.to_string(42) == "42"
        assert ConversionUtils.to_string([1, 2, 3]) == "[1, 2, 3]"

    def test_to_number(self):
        """Test conversion to number."""
        assert ConversionUtils.to_number(None) == 0.0
        assert ConversionUtils.to_number(True) == 1.0
        assert ConversionUtils.to_number("42") == 42.0
        assert ConversionUtils.to_number("invalid") == 0.0

    def test_to_boolean(self):
        """Test conversion to boolean."""
        assert ConversionUtils.to_boolean(None) is False
        assert ConversionUtils.to_boolean(True) is True
        assert ConversionUtils.to_boolean(0) is False
        assert ConversionUtils.to_boolean(1) is True
        assert ConversionUtils.to_boolean("") is False
        assert ConversionUtils.to_boolean("hello") is True

    def test_to_list(self):
        """Test conversion to list."""
        assert ConversionUtils.to_list(None) == []
        assert ConversionUtils.to_list([1, 2, 3]) == [1, 2, 3]
        assert ConversionUtils.to_list('["a", "b"]') == ["a", "b"]

    def test_deep_clone(self):
        """Test deep cloning."""
        original = {"a": [1, 2, 3], "b": {"c": "value"}}
        cloned = ConversionUtils.deep_clone(original)

        assert cloned == original
        assert cloned is not original
        assert cloned["a"] is not original["a"]

    def test_merge_dicts(self):
        """Test dictionary merging."""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}
        result = ConversionUtils.merge_dicts(base, override)

        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3
        assert result["e"] == 4


class TestLiteralExpressions:
    """Tests for literal expressions."""

    def test_null_expression(self):
        """Test null literal."""
        expr = NullExpression()
        assert expr.evaluate({}) is None

    def test_boolean_expression(self):
        """Test boolean literals."""
        true_expr = BooleanExpression(True)
        false_expr = BooleanExpression(False)

        assert true_expr.evaluate({}) is True
        assert false_expr.evaluate({}) is False

    def test_number_expression(self):
        """Test number literals."""
        int_expr = NumberExpression(42)
        float_expr = NumberExpression(3.14)

        assert int_expr.evaluate({}) == 42
        assert float_expr.evaluate({}) == 3.14

    def test_string_expression(self):
        """Test string literals."""
        expr = StringExpression("hello world")
        assert expr.evaluate({}) == "hello world"

    def test_array_expression(self):
        """Test array literals."""
        expr = ArrayExpression(elements=[
            NumberExpression(1),
            NumberExpression(2),
            NumberExpression(3),
        ])
        assert expr.evaluate({}) == [1, 2, 3]

    def test_object_expression(self):
        """Test object literals."""
        expr = ObjectExpression(properties={
            "name": StringExpression("John"),
            "age": NumberExpression(30),
        })
        result = expr.evaluate({})
        assert result == {"name": "John", "age": 30}


class TestOperatorExpressions:
    """Tests for operator expressions."""

    def test_arithmetic_operators(self):
        """Test arithmetic operators."""
        # Addition
        add = BinaryExpression(
            left=NumberExpression(10),
            operator=BinaryOperator.ADD,
            right=NumberExpression(5)
        )
        assert add.evaluate({}) == 15

        # Subtraction
        sub = BinaryExpression(
            left=NumberExpression(10),
            operator=BinaryOperator.SUBTRACT,
            right=NumberExpression(5)
        )
        assert sub.evaluate({}) == 5

        # Multiplication
        mul = BinaryExpression(
            left=NumberExpression(10),
            operator=BinaryOperator.MULTIPLY,
            right=NumberExpression(5)
        )
        assert mul.evaluate({}) == 50

        # Division
        div = BinaryExpression(
            left=NumberExpression(10),
            operator=BinaryOperator.DIVIDE,
            right=NumberExpression(5)
        )
        assert div.evaluate({}) == 2.0

    def test_comparison_operators(self):
        """Test comparison operators."""
        eq = BinaryExpression(
            left=NumberExpression(5),
            operator=BinaryOperator.EQUAL,
            right=NumberExpression(5)
        )
        assert eq.evaluate({}) is True

        lt = BinaryExpression(
            left=NumberExpression(3),
            operator=BinaryOperator.LESS,
            right=NumberExpression(5)
        )
        assert lt.evaluate({}) is True

        gt = BinaryExpression(
            left=NumberExpression(7),
            operator=BinaryOperator.GREATER,
            right=NumberExpression(5)
        )
        assert gt.evaluate({}) is True

    def test_logical_operators(self):
        """Test logical operators."""
        and_true = BinaryExpression(
            left=BooleanExpression(True),
            operator=BinaryOperator.AND,
            right=BooleanExpression(True)
        )
        assert and_true.evaluate({}) is True

        and_false = BinaryExpression(
            left=BooleanExpression(True),
            operator=BinaryOperator.AND,
            right=BooleanExpression(False)
        )
        assert and_false.evaluate({}) is False

        or_true = BinaryExpression(
            left=BooleanExpression(False),
            operator=BinaryOperator.OR,
            right=BooleanExpression(True)
        )
        assert or_true.evaluate({}) is True

    def test_unary_operators(self):
        """Test unary operators."""
        neg = UnaryExpression(
            operator=UnaryOperator.NEGATE,
            operand=NumberExpression(5)
        )
        assert neg.evaluate({}) == -5

        not_expr = UnaryExpression(
            operator=UnaryOperator.NOT,
            operand=BooleanExpression(True)
        )
        assert not_expr.evaluate({}) is False

    def test_ternary_expression(self):
        """Test ternary expression."""
        expr = TernaryExpression(
            condition=BooleanExpression(True),
            then_expr=StringExpression("yes"),
            else_expr=StringExpression("no")
        )
        assert expr.evaluate({}) == "yes"

        expr2 = TernaryExpression(
            condition=BooleanExpression(False),
            then_expr=StringExpression("yes"),
            else_expr=StringExpression("no")
        )
        assert expr2.evaluate({}) == "no"

    def test_string_concatenation(self):
        """Test string concatenation."""
        expr = BinaryExpression(
            left=StringExpression("Hello"),
            operator=BinaryOperator.CONCAT,
            right=StringExpression(" World")
        )
        assert expr.evaluate({}) == "Hello World"

    def test_null_coalescing(self):
        """Test null coalescing operator."""
        expr1 = BinaryExpression(
            left=NullExpression(),
            operator=BinaryOperator.NULL_COALESCE,
            right=StringExpression("default")
        )
        assert expr1.evaluate({}) == "default"

        expr2 = BinaryExpression(
            left=StringExpression("value"),
            operator=BinaryOperator.NULL_COALESCE,
            right=StringExpression("default")
        )
        assert expr2.evaluate({}) == "value"


class TestVariableExpressions:
    """Tests for variable expressions."""

    def test_variable_expression(self):
        """Test variable lookup."""
        expr = VariableExpression(name="x")
        assert expr.evaluate({"x": 42}) == 42

    def test_member_access(self):
        """Test member access."""
        obj = ObjectExpression(properties={"name": StringExpression("John")})
        expr = MemberAccessExpression(obj=obj, member="name")
        assert expr.evaluate({}) == "John"

    def test_index_access(self):
        """Test index access."""
        arr = ArrayExpression(elements=[NumberExpression(10), NumberExpression(20)])
        expr = IndexAccessExpression(obj=arr, index=NumberExpression(1))
        assert expr.evaluate({}) == 20

    def test_assignment(self):
        """Test assignment expression."""
        target = VariableExpression(name="x")
        value = NumberExpression(100)
        expr = AssignmentExpression(target=target, value=value)

        context = {}
        result = expr.evaluate(context)

        assert result == 100
        assert context["x"] == 100


class TestFunctionExpressions:
    """Tests for function expressions."""

    def test_function_call(self):
        """Test function call expression."""
        func = lambda x: x * 2
        expr = FunctionCallExpression(
            function=VariableExpression(name="double"),
            arguments=[NumberExpression(5)]
        )
        assert expr.evaluate({"double": func}) == 10

    def test_method_call_string(self):
        """Test string method calls."""
        expr = MethodCallExpression(
            obj=StringExpression("hello"),
            method="upper"
        )
        assert expr.evaluate({}) == "HELLO"

    def test_method_call_list(self):
        """Test list method calls."""
        expr = MethodCallExpression(
            obj=ArrayExpression(elements=[NumberExpression(1), NumberExpression(2)]),
            method="length"
        )
        assert expr.evaluate({}) == 2

    def test_function_definition(self):
        """Test function definition expression."""
        expr = FunctionDefinitionExpression(
            parameters=["x", "y"],
            body=BinaryExpression(
                left=VariableExpression(name="x"),
                operator=BinaryOperator.ADD,
                right=VariableExpression(name="y")
            )
        )

        func = expr.evaluate({})
        assert callable(func)
        assert func(3, 4) == 7


class TestControlFlowExpressions:
    """Tests for control flow expressions."""

    def test_block_expression(self):
        """Test block expression."""
        expr = BlockExpression(statements=[
            AssignmentExpression(
                target=VariableExpression(name="x"),
                value=NumberExpression(10)
            ),
            VariableExpression(name="x")
        ])

        context = {}
        result = expr.evaluate(context)

        assert result == 10
        assert context["x"] == 10

    def test_if_expression(self):
        """Test if expression."""
        expr_true = IfExpression(
            condition=BooleanExpression(True),
            then_branch=StringExpression("yes"),
            else_branch=StringExpression("no")
        )
        assert expr_true.evaluate({}) == "yes"

        expr_false = IfExpression(
            condition=BooleanExpression(False),
            then_branch=StringExpression("yes"),
            else_branch=StringExpression("no")
        )
        assert expr_false.evaluate({}) == "no"

    def test_for_each_expression(self):
        """Test for-each expression."""
        expr = ForExpression(
            variable="item",
            iterable=ArrayExpression(elements=[
                NumberExpression(1),
                NumberExpression(2),
                NumberExpression(3)
            ]),
            body=AssignmentExpression(
                target=VariableExpression(name="sum"),
                value=BinaryExpression(
                    left=VariableExpression(name="sum"),
                    operator=BinaryOperator.ADD,
                    right=VariableExpression(name="item")
                )
            )
        )

        context = {"sum": 0}
        expr.evaluate(context)

        assert context["sum"] == 6

    def test_while_expression(self):
        """Test while expression."""
        expr = WhileExpression(
            condition=BinaryExpression(
                left=VariableExpression(name="i"),
                operator=BinaryOperator.LESS,
                right=NumberExpression(3)
            ),
            body=AssignmentExpression(
                target=VariableExpression(name="i"),
                value=BinaryExpression(
                    left=VariableExpression(name="i"),
                    operator=BinaryOperator.ADD,
                    right=NumberExpression(1)
                )
            )
        )

        context = {"i": 0}
        expr.evaluate(context)

        assert context["i"] == 3


class TestClosures:
    """Tests for closure system."""

    def test_closure_context(self):
        """Test closure context."""
        ctx = ClosureContext()
        ctx.capture("x", 10)
        ctx.capture("y", 20)

        assert ctx.get("x") == 10
        assert ctx.get("y") == 20
        assert ctx.has("x") is True
        assert ctx.has("z") is False

    def test_closure(self):
        """Test closure creation and execution."""
        closure = Closure(
            parameters=["a"],
            body=lambda ctx: ctx["a"] + ctx["x"],
            context=ClosureContext(captured={"x": 10})
        )

        result = closure.call(5)
        assert result == 15

    def test_closure_builder(self):
        """Test closure builder."""
        closure = (
            ClosureBuilder()
            .with_parameter("x")
            .with_parameter("y")
            .capture("multiplier", 2)
            .with_body(lambda ctx: (ctx["x"] + ctx["y"]) * ctx["multiplier"])
            .build()
        )

        result = closure.call(3, 4)
        assert result == 14

    def test_closure_registry(self):
        """Test closure registry."""
        registry = ClosureRegistry()
        closure = Closure(
            name="add",
            parameters=["a", "b"],
            body=lambda ctx: ctx["a"] + ctx["b"]
        )

        registry.register(closure)

        assert registry.has("add") is True
        assert registry.get("add") is closure


class TestArrayGlobal:
    """Tests for Array global functions."""

    def test_array_create(self):
        """Test array creation."""
        arr = ArrayGlobal.create(1, 2, 3)
        assert arr == [1, 2, 3]

    def test_array_range(self):
        """Test array range."""
        arr = ArrayGlobal.range(0, 5)
        assert arr == [0, 1, 2, 3, 4]

    def test_array_operations(self):
        """Test array push/pop."""
        arr = [1, 2, 3]
        ArrayGlobal.push(arr, 4)
        assert arr == [1, 2, 3, 4]

        val = ArrayGlobal.pop(arr)
        assert val == 4
        assert arr == [1, 2, 3]

    def test_array_map_filter(self):
        """Test map and filter."""
        arr = [1, 2, 3, 4, 5]
        doubled = ArrayGlobal.map(arr, lambda x: x * 2)
        assert doubled == [2, 4, 6, 8, 10]

        evens = ArrayGlobal.filter(arr, lambda x: x % 2 == 0)
        assert evens == [2, 4]

    def test_array_reduce(self):
        """Test reduce."""
        arr = [1, 2, 3, 4, 5]
        total = ArrayGlobal.reduce(arr, lambda acc, x: acc + x, 0)
        assert total == 15


class TestJsonGlobal:
    """Tests for JSON global functions."""

    def test_json_parse(self):
        """Test JSON parsing."""
        result = JsonGlobal.parse('{"name": "John", "age": 30}')
        assert result == {"name": "John", "age": 30}

    def test_json_stringify(self):
        """Test JSON stringification."""
        result = JsonGlobal.stringify({"name": "John", "age": 30})
        assert '"name"' in result
        assert '"John"' in result

    def test_json_valid(self):
        """Test JSON validation."""
        assert JsonGlobal.valid('{"valid": true}') is True
        assert JsonGlobal.valid('{invalid json}') is False

    def test_json_get(self):
        """Test JSON get with path."""
        data = {"user": {"address": {"city": "New York"}}}
        result = JsonGlobal.get(data, "user.address.city")
        assert result == "New York"

    def test_json_merge(self):
        """Test JSON merge."""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}
        result = JsonGlobal.merge(base, override)

        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3


class TestExpressionEvaluator:
    """Tests for expression evaluator."""

    def test_evaluator_basic(self):
        """Test basic evaluation."""
        evaluator = ExpressionEvaluator()
        expr = NumberExpression(42)
        assert evaluator.evaluate(expr) == 42

    def test_evaluator_with_context(self):
        """Test evaluation with context."""
        evaluator = ExpressionEvaluator()
        expr = VariableExpression(name="x")

        result = evaluator.evaluate_with_context(expr, {"x": 100})
        assert result == 100

    def test_evaluator_complex_expression(self):
        """Test complex expression evaluation."""
        evaluator = ExpressionEvaluator()

        # (x + y) * z
        expr = BinaryExpression(
            left=BinaryExpression(
                left=VariableExpression(name="x"),
                operator=BinaryOperator.ADD,
                right=VariableExpression(name="y")
            ),
            operator=BinaryOperator.MULTIPLY,
            right=VariableExpression(name="z")
        )

        result = evaluator.evaluate_with_context(expr, {"x": 10, "y": 20, "z": 3})
        assert result == 90


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])