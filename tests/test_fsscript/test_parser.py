"""Unit tests for FSScript Parser."""

import pytest
from foggy.fsscript.parser import FsscriptParser, TokenType
from foggy.fsscript.expressions.literals import (
    NumberExpression,
    StringExpression,
    BooleanExpression,
    NullExpression,
    ArrayExpression,
    ObjectExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryExpression,
    UnaryExpression,
    TernaryExpression,
    BinaryOperator,
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
    ReturnExpression,
    BreakExpression,
    ContinueExpression,
)


class TestParserLiterals:
    """Test literal parsing."""

    def test_number(self):
        """Test number literal parsing."""
        parser = FsscriptParser("42")
        expr = parser.parse_expression()
        assert isinstance(expr, NumberExpression)
        assert expr.value == 42

    def test_float(self):
        """Test float literal parsing."""
        parser = FsscriptParser("3.14")
        expr = parser.parse_expression()
        assert isinstance(expr, NumberExpression)
        assert expr.value == 3.14

    def test_string_single_quote(self):
        """Test single-quoted string parsing."""
        parser = FsscriptParser("'hello'")
        expr = parser.parse_expression()
        assert isinstance(expr, StringExpression)
        assert expr.value == "hello"

    def test_string_double_quote(self):
        """Test double-quoted string parsing."""
        parser = FsscriptParser('"world"')
        expr = parser.parse_expression()
        assert isinstance(expr, StringExpression)
        assert expr.value == "world"

    def test_true(self):
        """Test true literal parsing."""
        parser = FsscriptParser("true")
        expr = parser.parse_expression()
        assert isinstance(expr, BooleanExpression)
        assert expr.value is True

    def test_false(self):
        """Test false literal parsing."""
        parser = FsscriptParser("false")
        expr = parser.parse_expression()
        assert isinstance(expr, BooleanExpression)
        assert expr.value is False

    def test_null(self):
        """Test null literal parsing."""
        parser = FsscriptParser("null")
        expr = parser.parse_expression()
        assert isinstance(expr, NullExpression)


class TestParserBinaryExpressions:
    """Test binary expression parsing."""

    def test_addition(self):
        """Test addition parsing."""
        parser = FsscriptParser("1 + 2")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.ADD
        assert isinstance(expr.left, NumberExpression)
        assert expr.left.value == 1
        assert isinstance(expr.right, NumberExpression)
        assert expr.right.value == 2

    def test_subtraction(self):
        """Test subtraction parsing."""
        parser = FsscriptParser("5 - 3")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.SUBTRACT

    def test_multiplication(self):
        """Test multiplication parsing."""
        parser = FsscriptParser("4 * 7")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.MULTIPLY

    def test_division(self):
        """Test division parsing."""
        parser = FsscriptParser("10 / 2")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.DIVIDE

    def test_precedence(self):
        """Test operator precedence (1 + 2 * 3 should be 1 + (2 * 3))."""
        parser = FsscriptParser("1 + 2 * 3")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.ADD
        assert isinstance(expr.right, BinaryExpression)
        assert expr.right.operator == BinaryOperator.MULTIPLY

    def test_parentheses(self):
        """Test parentheses override precedence ((1 + 2) * 3)."""
        parser = FsscriptParser("(1 + 2) * 3")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.MULTIPLY
        assert isinstance(expr.left, BinaryExpression)
        assert expr.left.operator == BinaryOperator.ADD

    def test_comparison(self):
        """Test comparison operators."""
        parser = FsscriptParser("a < b")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.LESS

    def test_equality(self):
        """Test equality operators."""
        parser = FsscriptParser("a == b")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.EQUAL

    def test_logical_and(self):
        """Test logical AND."""
        parser = FsscriptParser("a && b")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.AND

    def test_logical_or(self):
        """Test logical OR."""
        parser = FsscriptParser("a || b")
        expr = parser.parse_expression()
        assert isinstance(expr, BinaryExpression)
        assert expr.operator == BinaryOperator.OR


class TestParserUnaryExpressions:
    """Test unary expression parsing."""

    def test_negation(self):
        """Test numeric negation."""
        parser = FsscriptParser("-5")
        expr = parser.parse_expression()
        assert isinstance(expr, UnaryExpression)
        assert expr.operator.value == "-"

    def test_logical_not(self):
        """Test logical not."""
        parser = FsscriptParser("!flag")
        expr = parser.parse_expression()
        assert isinstance(expr, UnaryExpression)
        assert expr.operator.value == "!"


class TestParserTernary:
    """Test ternary expression parsing."""

    def test_simple_ternary(self):
        """Test simple ternary expression."""
        parser = FsscriptParser("a ? b : c")
        expr = parser.parse_expression()
        assert isinstance(expr, TernaryExpression)
        assert isinstance(expr.condition, VariableExpression)
        assert isinstance(expr.then_expr, VariableExpression)
        assert isinstance(expr.else_expr, VariableExpression)

    def test_nested_ternary(self):
        """Test nested ternary expression."""
        parser = FsscriptParser("a ? b : c ? d : e")
        expr = parser.parse_expression()
        assert isinstance(expr, TernaryExpression)
        assert isinstance(expr.else_expr, TernaryExpression)


class TestParserVariables:
    """Test variable and member access parsing."""

    def test_identifier(self):
        """Test identifier parsing."""
        parser = FsscriptParser("foo")
        expr = parser.parse_expression()
        assert isinstance(expr, VariableExpression)
        assert expr.name == "foo"

    def test_member_access(self):
        """Test member access parsing."""
        parser = FsscriptParser("obj.prop")
        expr = parser.parse_expression()
        assert isinstance(expr, MemberAccessExpression)
        assert isinstance(expr.obj, VariableExpression)
        assert expr.member == "prop"

    def test_chained_member_access(self):
        """Test chained member access."""
        parser = FsscriptParser("obj.prop1.prop2")
        expr = parser.parse_expression()
        assert isinstance(expr, MemberAccessExpression)
        assert isinstance(expr.obj, MemberAccessExpression)

    def test_index_access(self):
        """Test index access parsing."""
        parser = FsscriptParser("arr[0]")
        expr = parser.parse_expression()
        assert isinstance(expr, IndexAccessExpression)
        assert isinstance(expr.obj, VariableExpression)
        assert isinstance(expr.index, NumberExpression)

    def test_computed_member_access(self):
        """Test computed member access with variable index."""
        parser = FsscriptParser("obj[key]")
        expr = parser.parse_expression()
        assert isinstance(expr, IndexAccessExpression)
        assert isinstance(expr.index, VariableExpression)


class TestParserFunctionCalls:
    """Test function call parsing."""

    def test_simple_call(self):
        """Test simple function call."""
        parser = FsscriptParser("foo()")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionCallExpression)
        assert isinstance(expr.function, VariableExpression)
        assert len(expr.arguments) == 0

    def test_call_with_args(self):
        """Test function call with arguments."""
        parser = FsscriptParser("foo(1, 2)")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionCallExpression)
        assert len(expr.arguments) == 2

    def test_method_call(self):
        """Test method call parsing."""
        parser = FsscriptParser("obj.method()")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionCallExpression)

    def test_nested_call(self):
        """Test nested function call."""
        parser = FsscriptParser("foo(bar())")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionCallExpression)
        assert isinstance(expr.arguments[0], FunctionCallExpression)


class TestParserArrays:
    """Test array literal parsing."""

    def test_empty_array(self):
        """Test empty array literal."""
        parser = FsscriptParser("[]")
        expr = parser.parse_expression()
        assert isinstance(expr, ArrayExpression)
        assert len(expr.elements) == 0

    def test_simple_array(self):
        """Test simple array literal."""
        parser = FsscriptParser("[1, 2, 3]")
        expr = parser.parse_expression()
        assert isinstance(expr, ArrayExpression)
        assert len(expr.elements) == 3

    def test_nested_array(self):
        """Test nested array literal."""
        parser = FsscriptParser("[[1, 2], [3, 4]]")
        expr = parser.parse_expression()
        assert isinstance(expr, ArrayExpression)
        assert isinstance(expr.elements[0], ArrayExpression)


class TestParserObjects:
    """Test object literal parsing."""

    def test_empty_object(self):
        """Test empty object literal."""
        parser = FsscriptParser("{}")
        expr = parser.parse_expression()
        assert isinstance(expr, ObjectExpression)
        assert len(expr.properties) == 0

    def test_simple_object(self):
        """Test simple object literal."""
        parser = FsscriptParser("{a: 1, b: 2}")
        expr = parser.parse_expression()
        assert isinstance(expr, ObjectExpression)
        assert "a" in expr.properties
        assert "b" in expr.properties

    def test_object_with_identifier_values(self):
        """Test object with identifier values."""
        parser = FsscriptParser("{a: foo, b: bar}")
        expr = parser.parse_expression()
        assert isinstance(expr, ObjectExpression)
        assert isinstance(expr.properties["a"], VariableExpression)


class TestParserFunctions:
    """Test function definition parsing."""

    def test_simple_function(self):
        """Test simple function definition."""
        parser = FsscriptParser("function foo() { return 1; }")
        expr = parser.parse_statement()
        assert isinstance(expr, FunctionDefinitionExpression)

    def test_function_with_params(self):
        """Test function with parameters."""
        parser = FsscriptParser("function add(a, b) { return a + b; }")
        expr = parser.parse_statement()
        assert isinstance(expr, FunctionDefinitionExpression)
        assert len(expr.parameters) == 2

    def test_arrow_function(self):
        """Test arrow function parsing."""
        parser = FsscriptParser("(x) => x + 1")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionDefinitionExpression)

    def test_arrow_function_single_param(self):
        """Test arrow function with single parameter."""
        parser = FsscriptParser("x => x * 2")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionDefinitionExpression)
        assert len(expr.parameters) == 1


class TestParserControlFlow:
    """Test control flow parsing."""

    def test_if_statement(self):
        """Test if statement parsing."""
        parser = FsscriptParser("if (true) { 1; }")
        expr = parser.parse_statement()
        assert isinstance(expr, IfExpression)
        assert isinstance(expr.condition, BooleanExpression)
        assert isinstance(expr.then_branch, BlockExpression)

    def test_if_else(self):
        """Test if-else statement."""
        parser = FsscriptParser("if (a) { 1; } else { 2; }")
        expr = parser.parse_statement()
        assert isinstance(expr, IfExpression)
        assert expr.else_branch is not None

    def test_if_else_if(self):
        """Test if-else-if chain."""
        parser = FsscriptParser("if (a) { 1; } else if (b) { 2; } else { 3; }")
        expr = parser.parse_statement()
        assert isinstance(expr, IfExpression)
        assert isinstance(expr.else_branch, IfExpression)

    def test_for_loop(self):
        """Test for loop parsing."""
        parser = FsscriptParser("for (var i = 0; i < 10; i++) { }")
        expr = parser.parse_statement()
        assert isinstance(expr, ForExpression)

    def test_for_in(self):
        """Test for-in loop parsing."""
        parser = FsscriptParser("for (var k in obj) { }")
        expr = parser.parse_statement()
        assert isinstance(expr, ForExpression)

    def test_while_loop(self):
        """Test while loop parsing."""
        parser = FsscriptParser("while (x < 10) { x++; }")
        expr = parser.parse_statement()
        assert isinstance(expr, WhileExpression)

    def test_return_statement(self):
        """Test return statement parsing."""
        parser = FsscriptParser("return 42;")
        expr = parser.parse_statement()
        assert isinstance(expr, ReturnExpression)
        assert isinstance(expr.value, NumberExpression)

    def test_break_statement(self):
        """Test break statement parsing."""
        parser = FsscriptParser("break;")
        expr = parser.parse_statement()
        assert isinstance(expr, BreakExpression)

    def test_continue_statement(self):
        """Test continue statement parsing."""
        parser = FsscriptParser("continue;")
        expr = parser.parse_statement()
        assert isinstance(expr, ContinueExpression)


class TestParserDeclarations:
    """Test variable declaration parsing."""

    def test_var_declaration(self):
        """Test var declaration."""
        parser = FsscriptParser("var x = 1;")
        expr = parser.parse_statement()
        assert isinstance(expr, AssignmentExpression)

    def test_let_declaration(self):
        """Test let declaration."""
        parser = FsscriptParser("let y = 2;")
        expr = parser.parse_statement()
        assert isinstance(expr, AssignmentExpression)

    def test_const_declaration(self):
        """Test const declaration."""
        parser = FsscriptParser("const z = 3;")
        expr = parser.parse_statement()
        assert isinstance(expr, AssignmentExpression)


class TestParserBlocks:
    """Test block parsing."""

    def test_empty_block(self):
        """Test empty block."""
        parser = FsscriptParser("{}")
        expr = parser.parse_statement()
        assert isinstance(expr, BlockExpression)
        assert len(expr.statements) == 0

    def test_block_with_statements(self):
        """Test block with statements."""
        parser = FsscriptParser("{ var x = 1; var y = 2; }")
        expr = parser.parse_statement()
        assert isinstance(expr, BlockExpression)
        assert len(expr.statements) == 2


class TestParserProgram:
    """Test program parsing."""

    def test_empty_program(self):
        """Test empty program."""
        parser = FsscriptParser("")
        expr = parser.parse_program()
        assert isinstance(expr, BlockExpression)
        assert len(expr.statements) == 0

    def test_multiple_statements(self):
        """Test program with multiple statements."""
        parser = FsscriptParser("var x = 1; var y = 2;")
        expr = parser.parse_program()
        assert isinstance(expr, BlockExpression)
        assert len(expr.statements) == 2


class TestParserComplex:
    """Test complex expression parsing."""

    def test_chained_method_calls(self):
        """Test chained method calls."""
        parser = FsscriptParser("arr.map(x => x * 2).filter(x => x > 5)")
        expr = parser.parse_expression()
        assert isinstance(expr, FunctionCallExpression)

    def test_object_destructuring_in_var(self):
        """Test object destructuring pattern."""
        parser = FsscriptParser("const {a, b} = obj;")
        expr = parser.parse_statement()
        # Destructuring is simplified
        assert expr is not None

    def test_function_with_default_params(self):
        """Test function with default parameters."""
        parser = FsscriptParser("function foo(x = 0, y = 1) { return x + y; }")
        expr = parser.parse_statement()
        assert isinstance(expr, FunctionDefinitionExpression)

    def test_ternary_in_expression(self):
        """Test ternary within larger expression."""
        parser = FsscriptParser("a ? b : c + d")
        expr = parser.parse_expression()
        assert isinstance(expr, TernaryExpression)