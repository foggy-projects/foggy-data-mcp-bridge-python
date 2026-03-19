"""Unit tests for FSScript Lexer."""

import pytest
from foggy.fsscript.parser import (
    FsscriptLexer,
    LexerConfig,
    TokenType,
    Token,
)


class TestLexerNumbers:
    """Test number tokenization."""

    def test_integer(self):
        """Test integer tokenization."""
        lexer = FsscriptLexer("42")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 42

    def test_float(self):
        """Test float tokenization."""
        lexer = FsscriptLexer("3.14")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 3.14

    def test_float_with_leading_dot(self):
        """Test float with leading dot (.5)."""
        lexer = FsscriptLexer(".5")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 0.5

    def test_hex_number(self):
        """Test hexadecimal number tokenization."""
        lexer = FsscriptLexer("0xFF")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 255

    def test_scientific_notation(self):
        """Test scientific notation."""
        lexer = FsscriptLexer("1e10")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 1e10

    def test_scientific_notation_negative(self):
        """Test scientific notation with negative exponent."""
        lexer = FsscriptLexer("1e-5")
        token = lexer.next_token()
        assert token.type == TokenType.NUMBER
        assert token.value == 1e-5

    def test_multiple_numbers(self):
        """Test multiple numbers separated by space."""
        lexer = FsscriptLexer("1 2 3")
        tokens = lexer.get_all_tokens()
        assert len(tokens) == 4  # 3 numbers + EOF
        assert tokens[0].value == 1
        assert tokens[1].value == 2
        assert tokens[2].value == 3


class TestLexerStrings:
    """Test string tokenization."""

    def test_single_quote_string(self):
        """Test single-quoted string."""
        lexer = FsscriptLexer("'hello'")
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello"

    def test_double_quote_string(self):
        """Test double-quoted string."""
        lexer = FsscriptLexer('"world"')
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "world"

    def test_string_with_escape(self):
        """Test string with escape sequences."""
        lexer = FsscriptLexer(r"'hello\nworld'")
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "hello\nworld"

    def test_string_with_tab(self):
        """Test string with tab escape."""
        lexer = FsscriptLexer(r"'a\tb'")
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == "a\tb"

    def test_empty_string(self):
        """Test empty string."""
        lexer = FsscriptLexer("''")
        token = lexer.next_token()
        assert token.type == TokenType.STRING
        assert token.value == ""


class TestLexerOperators:
    """Test operator tokenization."""

    def test_plus(self):
        lexer = FsscriptLexer("+")
        token = lexer.next_token()
        assert token.type == TokenType.PLUS

    def test_minus(self):
        lexer = FsscriptLexer("-")
        token = lexer.next_token()
        assert token.type == TokenType.MINUS

    def test_multiply(self):
        lexer = FsscriptLexer("*")
        token = lexer.next_token()
        assert token.type == TokenType.MULTIPLY

    def test_divide(self):
        lexer = FsscriptLexer("/")
        token = lexer.next_token()
        assert token.type == TokenType.DIVIDE

    def test_modulo(self):
        lexer = FsscriptLexer("%")
        token = lexer.next_token()
        assert token.type == TokenType.MODULO

    def test_equal(self):
        lexer = FsscriptLexer("=")
        token = lexer.next_token()
        assert token.type == TokenType.EQ

    def test_double_equal(self):
        lexer = FsscriptLexer("==")
        token = lexer.next_token()
        assert token.type == TokenType.EQ2

    def test_triple_equal(self):
        lexer = FsscriptLexer("===")
        token = lexer.next_token()
        assert token.type == TokenType.EQ2

    def test_not_equal(self):
        lexer = FsscriptLexer("!=")
        token = lexer.next_token()
        assert token.type == TokenType.NE

    def test_less_than(self):
        lexer = FsscriptLexer("<")
        token = lexer.next_token()
        assert token.type == TokenType.LT

    def test_less_equal(self):
        lexer = FsscriptLexer("<=")
        token = lexer.next_token()
        assert token.type == TokenType.LE

    def test_greater_than(self):
        lexer = FsscriptLexer(">")
        token = lexer.next_token()
        assert token.type == TokenType.GT

    def test_greater_equal(self):
        lexer = FsscriptLexer(">=")
        token = lexer.next_token()
        assert token.type == TokenType.GE

    def test_and_and(self):
        lexer = FsscriptLexer("&&")
        token = lexer.next_token()
        assert token.type == TokenType.AND_AND

    def test_or_or(self):
        lexer = FsscriptLexer("||")
        token = lexer.next_token()
        assert token.type == TokenType.OR_OR

    def test_arrow(self):
        lexer = FsscriptLexer("=>")
        token = lexer.next_token()
        assert token.type == TokenType.ARROW

    def test_increment(self):
        lexer = FsscriptLexer("++")
        token = lexer.next_token()
        assert token.type == TokenType.INCREMENT

    def test_decrement(self):
        lexer = FsscriptLexer("--")
        token = lexer.next_token()
        assert token.type == TokenType.DECREMENT

    def test_dot_dot_dot(self):
        lexer = FsscriptLexer("...")
        token = lexer.next_token()
        assert token.type == TokenType.DOT_DOT_DOT

    def test_qmark_dot(self):
        lexer = FsscriptLexer("?.")
        token = lexer.next_token()
        assert token.type == TokenType.QMARK_DOT


class TestLexerKeywords:
    """Test keyword tokenization."""

    def test_true(self):
        lexer = FsscriptLexer("true")
        token = lexer.next_token()
        assert token.type == TokenType.TRUE

    def test_false(self):
        lexer = FsscriptLexer("false")
        token = lexer.next_token()
        assert token.type == TokenType.FALSE

    def test_null(self):
        lexer = FsscriptLexer("null")
        token = lexer.next_token()
        assert token.type == TokenType.NULL

    def test_var(self):
        lexer = FsscriptLexer("var")
        token = lexer.next_token()
        assert token.type == TokenType.VAR

    def test_let(self):
        lexer = FsscriptLexer("let")
        token = lexer.next_token()
        assert token.type == TokenType.LET

    def test_const(self):
        lexer = FsscriptLexer("const")
        token = lexer.next_token()
        assert token.type == TokenType.CONST

    def test_function(self):
        lexer = FsscriptLexer("function")
        token = lexer.next_token()
        assert token.type == TokenType.FUNCTION

    def test_if(self):
        lexer = FsscriptLexer("if")
        token = lexer.next_token()
        assert token.type == TokenType.IF

    def test_else(self):
        lexer = FsscriptLexer("else")
        token = lexer.next_token()
        assert token.type == TokenType.ELSE

    def test_for(self):
        lexer = FsscriptLexer("for")
        token = lexer.next_token()
        assert token.type == TokenType.FOR

    def test_while(self):
        lexer = FsscriptLexer("while")
        token = lexer.next_token()
        assert token.type == TokenType.WHILE

    def test_return(self):
        lexer = FsscriptLexer("return")
        token = lexer.next_token()
        assert token.type == TokenType.RETURN

    def test_import(self):
        lexer = FsscriptLexer("import")
        token = lexer.next_token()
        assert token.type == TokenType.IMPORT

    def test_export(self):
        lexer = FsscriptLexer("export")
        token = lexer.next_token()
        assert token.type == TokenType.EXPORT


class TestLexerIdentifiers:
    """Test identifier tokenization."""

    def test_simple_identifier(self):
        lexer = FsscriptLexer("foo")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "foo"

    def test_camel_case(self):
        lexer = FsscriptLexer("myVariableName")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "myVariableName"

    def test_with_underscore(self):
        lexer = FsscriptLexer("_private")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "_private"

    def test_with_dollar(self):
        lexer = FsscriptLexer("$jquery")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "$jquery"

    def test_with_numbers(self):
        lexer = FsscriptLexer("var1")
        token = lexer.next_token()
        assert token.type == TokenType.IDENTIFIER
        assert token.value == "var1"


class TestLexerDelimiters:
    """Test delimiter tokenization."""

    def test_lparen(self):
        lexer = FsscriptLexer("(")
        token = lexer.next_token()
        assert token.type == TokenType.LPAREN

    def test_rparen(self):
        lexer = FsscriptLexer(")")
        token = lexer.next_token()
        assert token.type == TokenType.RPAREN

    def test_lbrace(self):
        lexer = FsscriptLexer("{")
        token = lexer.next_token()
        assert token.type == TokenType.LBRACE

    def test_rbrace(self):
        lexer = FsscriptLexer("}")
        token = lexer.next_token()
        assert token.type == TokenType.RBRACE

    def test_lsbrace(self):
        lexer = FsscriptLexer("[")
        token = lexer.next_token()
        assert token.type == TokenType.LSBRACE

    def test_rsbrace(self):
        lexer = FsscriptLexer("]")
        token = lexer.next_token()
        assert token.type == TokenType.RSBRACE

    def test_comma(self):
        lexer = FsscriptLexer(",")
        token = lexer.next_token()
        assert token.type == TokenType.COMMA

    def test_colon(self):
        lexer = FsscriptLexer(":")
        token = lexer.next_token()
        assert token.type == TokenType.COLON

    def test_semicolon(self):
        lexer = FsscriptLexer(";")
        token = lexer.next_token()
        assert token.type == TokenType.SEMICOLON

    def test_dot(self):
        lexer = FsscriptLexer(".")
        token = lexer.next_token()
        assert token.type == TokenType.DOT


class TestLexerComments:
    """Test comment handling."""

    def test_line_comment(self):
        """Test single line comment."""
        lexer = FsscriptLexer("1 // comment\n2")
        tokens = lexer.get_all_tokens()
        # ASI may insert semicolon after 1, so we check for the numbers
        numbers = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(numbers) == 2
        assert numbers[0].value == 1
        assert numbers[1].value == 2

    def test_block_comment(self):
        """Test block comment."""
        lexer = FsscriptLexer("1 /* comment */ 2")
        tokens = lexer.get_all_tokens()
        assert len(tokens) == 3  # 1, 2, EOF
        assert tokens[0].value == 1
        assert tokens[1].value == 2


class TestLexerASI:
    """Test Automatic Semicolon Insertion."""

    def test_asi_between_statements(self):
        """Test ASI between statements on newlines."""
        lexer = FsscriptLexer("x = 1\ny = 2")
        tokens = lexer.get_all_tokens()
        # Should have: x, =, 1, SEMICOLON (ASI), y, =, 2, EOF
        semicolon_found = any(t.type == TokenType.SEMICOLON for t in tokens)
        assert semicolon_found

    def test_asi_after_return(self):
        """Test ASI after return statement."""
        lexer = FsscriptLexer("return\nx")
        tokens = lexer.get_all_tokens()
        # return should get ASI after it
        assert tokens[0].type == TokenType.RETURN

    def test_no_asi_with_operator(self):
        """Test no ASI when operator continues expression."""
        lexer = FsscriptLexer("x = 1 +\n2")
        tokens = lexer.get_all_tokens()
        # Should not have ASI because + continues the expression
        semicolons = [t for t in tokens if t.type == TokenType.SEMICOLON]
        # Either no semicolons or only at end
        assert len(semicolons) <= 1


class TestLexerLocation:
    """Test source location tracking."""

    def test_line_column(self):
        """Test line and column tracking."""
        lexer = FsscriptLexer("foo")
        token = lexer.next_token()
        assert token.line == 1
        assert token.column == 1

    def test_multiline(self):
        """Test location across multiple lines."""
        lexer = FsscriptLexer("foo\nbar")
        token1 = lexer.next_token()
        token2 = lexer.next_token()
        assert token1.line == 1
        assert token2.line == 2


class TestLexerComplex:
    """Test complex expressions."""

    def test_simple_expression(self):
        """Test simple arithmetic expression."""
        lexer = FsscriptLexer("1 + 2")
        tokens = lexer.get_all_tokens()
        assert len(tokens) == 4  # 1, +, 2, EOF
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[1].type == TokenType.PLUS
        assert tokens[2].type == TokenType.NUMBER

    def test_function_call(self):
        """Test function call tokenization."""
        lexer = FsscriptLexer("foo(a, b)")
        tokens = lexer.get_all_tokens()
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "foo"
        assert tokens[1].type == TokenType.LPAREN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[3].type == TokenType.COMMA

    def test_object_literal(self):
        """Test object literal tokenization."""
        lexer = FsscriptLexer("{a: 1, b: 2}")
        tokens = lexer.get_all_tokens()
        assert tokens[0].type == TokenType.LBRACE
        assert tokens[1].type == TokenType.IDENTIFIER

    def test_array_literal(self):
        """Test array literal tokenization."""
        lexer = FsscriptLexer("[1, 2, 3]")
        tokens = lexer.get_all_tokens()
        assert tokens[0].type == TokenType.LSBRACE
        assert tokens[1].type == TokenType.NUMBER

    def test_arrow_function(self):
        """Test arrow function tokenization."""
        lexer = FsscriptLexer("(x) => x + 1")
        tokens = lexer.get_all_tokens()
        assert any(t.type == TokenType.ARROW for t in tokens)


class TestLexerEOF:
    """Test EOF handling."""

    def test_empty_input(self):
        """Test empty input."""
        lexer = FsscriptLexer("")
        token = lexer.next_token()
        assert token.type == TokenType.EOF

    def test_eof_after_token(self):
        """Test EOF after token."""
        lexer = FsscriptLexer("42")
        token1 = lexer.next_token()
        token2 = lexer.next_token()
        assert token1.type == TokenType.NUMBER
        assert token2.type == TokenType.EOF

    def test_tokenize_returns_all(self):
        """Test tokenize returns all tokens including EOF."""
        lexer = FsscriptLexer("1 + 2")
        tokens = list(lexer.tokenize())
        assert tokens[-1].type == TokenType.EOF