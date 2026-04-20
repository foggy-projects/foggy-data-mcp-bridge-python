"""Tests for `foggy.fsscript.parser.dialect` (Scanner-level dialect API).

Covers the per-parser keyword-override mechanism that lets callers (e.g. the
formula compiler) declare "in this context `if` is a function name, not a
control-flow keyword" without resorting to source-string preprocessing.

Test categories
===============
- TestEffectiveKeywords: pure data-layer behavior of ``FsscriptDialect``.
- TestDefaultDialect: behavior parity with no-dialect / historical FSScript.
- TestSqlExpressionDialect: ``SQL_EXPRESSION_DIALECT`` allowing ``if`` as IDENTIFIER.
- TestNaturalProtections: lexer-level guarantees the prior char-state-machine
  preprocessor was hand-coded to provide (string literals, word boundaries),
  proving the dialect path inherits them for free.
"""

from __future__ import annotations

import pytest

from foggy.fsscript.expressions.functions import FunctionCallExpression
from foggy.fsscript.expressions.literals import (
    NumberExpression,
    StringExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryExpression,
    BinaryOperator,
)
from foggy.fsscript.expressions.variables import VariableExpression
from foggy.fsscript.parser import (
    DEFAULT_DIALECT,
    KEYWORDS,
    SQL_EXPRESSION_DIALECT,
    FsscriptDialect,
    FsscriptParser,
    ParseError,
    TokenType,
)


# --------------------------------------------------------------------------- #
# TestEffectiveKeywords — data-layer behavior of FsscriptDialect
# --------------------------------------------------------------------------- #


class TestEffectiveKeywords:
    """``FsscriptDialect.effective_keywords()`` merge semantics."""

    def test_default_returns_value_equal_to_keywords(self) -> None:
        """``DEFAULT_DIALECT`` (empty override) returns a dict value-equal to KEYWORDS."""
        eff = DEFAULT_DIALECT.effective_keywords()
        assert eff == dict(KEYWORDS)

    def test_returned_dict_is_not_module_constant(self) -> None:
        """The cached merged dict is a distinct object from the KEYWORDS constant.

        Contract: ``effective_keywords()`` returns a per-instance cached dict
        that is shared across calls (do not mutate it), but it is NOT the same
        object as the module-level ``KEYWORDS``. This isolation matters because
        a dialect with overrides would otherwise corrupt KEYWORDS.
        """
        eff = DEFAULT_DIALECT.effective_keywords()
        assert eff is not KEYWORDS
        # Same object on repeated calls (the cache).
        assert DEFAULT_DIALECT.effective_keywords() is eff

    def test_none_value_removes_key(self) -> None:
        """An override value of ``None`` removes that key from the merged dict."""
        d = FsscriptDialect(name="t", keywords_override={"if": None})
        eff = d.effective_keywords()
        assert "if" not in eff
        # Other keywords are untouched
        assert eff["true"] == TokenType.TRUE
        assert eff["in"] == TokenType.IN

    def test_token_type_value_overrides_key(self) -> None:
        """An override value of TokenType replaces the existing mapping."""
        d = FsscriptDialect(
            name="t",
            keywords_override={"like": TokenType.IDENTIFIER},
        )
        eff = d.effective_keywords()
        assert eff["like"] == TokenType.IDENTIFIER
        # Sanity: KEYWORDS still maps `like` to LIKE
        assert KEYWORDS["like"] == TokenType.LIKE

    def test_unknown_key_in_override_is_added(self) -> None:
        """Override may *add* a brand-new keyword that didn't exist before."""
        d = FsscriptDialect(
            name="t",
            keywords_override={"foobar": TokenType.IDENTIFIER},
        )
        eff = d.effective_keywords()
        assert eff["foobar"] == TokenType.IDENTIFIER
        assert "foobar" not in KEYWORDS

    def test_remove_missing_key_is_noop(self) -> None:
        """Removing a key that isn't in KEYWORDS is silently ignored."""
        d = FsscriptDialect(
            name="t",
            keywords_override={"never_was_a_keyword": None},
        )
        # Must not raise; merged dict equals KEYWORDS
        eff = d.effective_keywords()
        assert eff == dict(KEYWORDS)

    def test_dialect_is_frozen(self) -> None:
        """``FsscriptDialect`` is immutable: cannot reassign fields.

        Guards thread-safety guarantees of module-level singletons against an
        accidental future removal of ``frozen=True``.
        """
        with pytest.raises(Exception):  # FrozenInstanceError
            DEFAULT_DIALECT.name = "mutated"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# TestDefaultDialect — historical behavior preserved
# --------------------------------------------------------------------------- #


class TestDefaultDialect:
    """Parity between no-dialect, ``DEFAULT_DIALECT``, and historical FSScript."""

    def test_no_dialect_treats_if_as_reserved(self) -> None:
        """Bare ``if(...)`` at expression position is rejected (IF is reserved)."""
        parser = FsscriptParser("if(a, 1, 0)")
        with pytest.raises(ParseError):
            parser.parse_expression()

    def test_explicit_default_treats_if_as_reserved(self) -> None:
        """``dialect=DEFAULT_DIALECT`` matches no-dialect behavior."""
        parser = FsscriptParser("if(a, 1, 0)", dialect=DEFAULT_DIALECT)
        with pytest.raises(ParseError):
            parser.parse_expression()

    def test_no_dialect_and_default_produce_same_ast(self) -> None:
        """For non-keyword expressions, ``None`` and ``DEFAULT_DIALECT`` produce
        identical ASTs."""
        tree_none = FsscriptParser("a + b * c").parse_expression()
        tree_default = FsscriptParser("a + b * c", dialect=DEFAULT_DIALECT).parse_expression()
        # Same shape, same operands. Repr is sufficient for structural equality
        # because both are pydantic BaseModel-derived Expressions.
        assert repr(tree_none) == repr(tree_default)

    def test_default_dialect_lexer_keywords_points_at_module_constant(self) -> None:
        """Performance-sensitive contract: ``dialect=None`` does NOT copy KEYWORDS.

        This guards against a future refactor accidentally introducing a per-
        parse copy. The fast path is to share the module constant by reference.
        """
        parser = FsscriptParser("a + b")
        # White-box check on the lexer keywords binding
        assert parser._lexer._keywords is KEYWORDS  # noqa: SLF001


# --------------------------------------------------------------------------- #
# TestSqlExpressionDialect — `if` is a normal function name
# --------------------------------------------------------------------------- #


class TestSqlExpressionDialect:
    """Behavior of the predefined ``SQL_EXPRESSION_DIALECT`` dialect."""

    def test_if_parses_as_function_call(self) -> None:
        """``if(c, a, b)`` becomes a FunctionCallExpression with VariableExpression('if')."""
        tree = FsscriptParser("if(a, 1, 0)", dialect=SQL_EXPRESSION_DIALECT).parse_expression()
        assert isinstance(tree, FunctionCallExpression)
        assert isinstance(tree.function, VariableExpression)
        assert tree.function.name == "if"
        assert len(tree.arguments) == 3

    def test_if_at_expression_start(self) -> None:
        """``if(...)`` at column 1 still parses (no leading-char prerequisite)."""
        tree = FsscriptParser("if(x > 0, 1, 0)", dialect=SQL_EXPRESSION_DIALECT).parse_expression()
        assert isinstance(tree, FunctionCallExpression)
        assert tree.function.name == "if"

    def test_if_after_operator(self) -> None:
        """``a + if(...)`` — the ``if`` after a binary operator still parses."""
        tree = FsscriptParser(
            "a + if(b > 0, 1, 0)", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        # Outermost is BinaryExpression(ADD)
        assert isinstance(tree, BinaryExpression)
        assert tree.operator == BinaryOperator.ADD
        # Right side is the if(...) function call
        assert isinstance(tree.right, FunctionCallExpression)
        assert isinstance(tree.right.function, VariableExpression)
        assert tree.right.function.name == "if"

    def test_multiple_if_calls_in_one_expression(self) -> None:
        """Multiple ``if(...)`` calls coexist in a single expression."""
        tree = FsscriptParser(
            "if(a, 1, 0) + if(b, 2, 0)", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        assert isinstance(tree, BinaryExpression)
        assert isinstance(tree.left, FunctionCallExpression)
        assert isinstance(tree.right, FunctionCallExpression)
        assert tree.left.function.name == "if"  # type: ignore[attr-defined]
        assert tree.right.function.name == "if"  # type: ignore[attr-defined]

    def test_other_reserved_words_still_reserved(self) -> None:
        """Only ``if`` is removed. ``switch`` etc. remain reserved."""
        # `switch(...)` would attempt to parse as a switch statement — not legal
        # at expression position. Should raise.
        with pytest.raises(ParseError):
            FsscriptParser("switch(a)", dialect=SQL_EXPRESSION_DIALECT).parse_expression()

    def test_in_remains_an_operator(self) -> None:
        """``in`` is still a binary operator under SQL_EXPRESSION_DIALECT (not removed)."""
        tree = FsscriptParser(
            "v in (1, 2, 3)", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        assert isinstance(tree, BinaryExpression)
        assert tree.operator == BinaryOperator.IN

    def test_null_true_false_still_keyword_literals(self) -> None:
        """``null`` / ``true`` / ``false`` still parse as keyword literals."""
        from foggy.fsscript.expressions.literals import (
            BooleanExpression,
            NullExpression,
        )

        assert isinstance(
            FsscriptParser("null", dialect=SQL_EXPRESSION_DIALECT).parse_expression(),
            NullExpression,
        )
        assert isinstance(
            FsscriptParser("true", dialect=SQL_EXPRESSION_DIALECT).parse_expression(),
            BooleanExpression,
        )
        assert isinstance(
            FsscriptParser("false", dialect=SQL_EXPRESSION_DIALECT).parse_expression(),
            BooleanExpression,
        )

    def test_lexer_keywords_does_not_contain_if(self) -> None:
        """White-box: under SQL_EXPRESSION_DIALECT the lexer's effective keyword dict
        excludes ``if`` (so the lexer never emits TokenType.IF for it)."""
        parser = FsscriptParser("anything", dialect=SQL_EXPRESSION_DIALECT)
        assert "if" not in parser._lexer._keywords  # noqa: SLF001
        # And it is NOT the same object as KEYWORDS (it's a materialized copy)
        assert parser._lexer._keywords is not KEYWORDS  # noqa: SLF001

    def test_template_string_inherits_dialect(self) -> None:
        """`${if(...)}` inside a template string must follow the outer dialect.

        Without dialect inheritance in `_parse_template_string`, the nested
        FsscriptParser would silently use the default keyword set and reject
        ``if`` as a control-flow keyword.
        """
        from foggy.fsscript.expressions.literals import TemplateLiteralExpression

        tree = FsscriptParser(
            "`prefix ${if(a, 1, 0)} suffix`", dialect=SQL_EXPRESSION_DIALECT,
        ).parse_expression()
        assert isinstance(tree, TemplateLiteralExpression)
        # Among the parts, locate the embedded expression and assert it parsed
        # as a function call (not fell back to a string literal on parse error).
        embedded = [p for p in tree.parts if isinstance(p, FunctionCallExpression)]
        assert len(embedded) == 1
        assert embedded[0].function.name == "if"  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# TestNaturalProtections — protections inherited from the lexer for free
# --------------------------------------------------------------------------- #


class TestNaturalProtections:
    """Edge cases the historical char-state-machine preprocessor explicitly
    guarded against. With the dialect approach, lexer tokenization handles
    them naturally and these tests document that contract.
    """

    def test_string_literal_with_if_is_unaffected(self) -> None:
        """``if`` inside a STRING token is never inspected as a keyword."""
        tree = FsscriptParser(
            "'has if(x) inside'", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        assert isinstance(tree, StringExpression)
        assert tree.value == "has if(x) inside"

    def test_string_literal_with_iif_is_unaffected(self) -> None:
        """Mirror of the above — verifies no historical IIF alias leaks through."""
        tree = FsscriptParser(
            "'verbatim IIF here'", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        assert isinstance(tree, StringExpression)
        assert tree.value == "verbatim IIF here"

    def test_identifier_starting_with_if_is_not_split(self) -> None:
        """``ifnull`` is one IDENTIFIER token — never confused with ``if``."""
        # `ifnull(a, 0)` parses as a function call to `ifnull` (single identifier)
        tree = FsscriptParser(
            "ifnull(a, 0)", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        assert isinstance(tree, FunctionCallExpression)
        assert isinstance(tree.function, VariableExpression)
        assert tree.function.name == "ifnull"

    def test_identifier_ending_with_if_is_not_split(self) -> None:
        """``gift(x)`` is one IDENTIFIER token — the trailing ``if`` substring
        within ``gift`` does not match the keyword."""
        tree = FsscriptParser("gift(x)", dialect=SQL_EXPRESSION_DIALECT).parse_expression()
        assert isinstance(tree, FunctionCallExpression)
        assert isinstance(tree.function, VariableExpression)
        assert tree.function.name == "gift"

    def test_underscore_prefixed_if_is_one_identifier(self) -> None:
        """``_if_(x)`` is one IDENTIFIER (underscore is identifier-continuing)."""
        tree = FsscriptParser("_if_(x)", dialect=SQL_EXPRESSION_DIALECT).parse_expression()
        assert isinstance(tree, FunctionCallExpression)
        assert isinstance(tree.function, VariableExpression)
        assert tree.function.name == "_if_"

    def test_if_as_string_argument(self) -> None:
        """``if(s == 'contains if(x) here', 1, 0)`` — the inner string holds
        ``if(`` literally without disturbing the outer single ``if`` call."""
        tree = FsscriptParser(
            "if(s == 'contains if(x) here', 1, 0)", dialect=SQL_EXPRESSION_DIALECT
        ).parse_expression()
        assert isinstance(tree, FunctionCallExpression)
        assert tree.function.name == "if"  # type: ignore[attr-defined]
        # Comparison string preserved verbatim
        cmp = tree.arguments[0]
        assert isinstance(cmp, BinaryExpression)
        assert isinstance(cmp.right, StringExpression)
        assert cmp.right.value == "contains if(x) here"
        # Numeric branches preserved
        assert isinstance(tree.arguments[1], NumberExpression)
        assert tree.arguments[1].value == 1
        assert isinstance(tree.arguments[2], NumberExpression)
        assert tree.arguments[2].value == 0
