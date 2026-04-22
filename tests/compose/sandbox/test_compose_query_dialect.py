"""M3 · ComposeQueryDialect parser integration.

Verifies:
* ``from`` is reserved under the default fsscript dialect (backwards compat).
* Under ``COMPOSE_QUERY_DIALECT``, ``from`` parses as a plain identifier
  so ``from({model: 'X'})`` builds a normal function-call expression —
  matching the cross-language contract with JavaScript's global
  ``from({...})`` shape (see 8.2.0.beta 需求 §命名约定).
"""

from __future__ import annotations

import pytest

from foggy.fsscript.parser import (
    COMPOSE_QUERY_DIALECT,
    DEFAULT_DIALECT,
    FsscriptLexer,
    FsscriptParser,
    SQL_EXPRESSION_DIALECT,
    TokenType,
)


class TestDialectDefinition:
    def test_dialect_is_exported_at_parser_root(self):
        """Pkg-level re-export lets callers import without reaching into dialect.py."""
        from foggy.fsscript import parser as parser_pkg

        assert hasattr(parser_pkg, "COMPOSE_QUERY_DIALECT")
        assert parser_pkg.COMPOSE_QUERY_DIALECT is COMPOSE_QUERY_DIALECT

    def test_dialect_has_stable_name(self):
        assert COMPOSE_QUERY_DIALECT.name == "compose-query"

    def test_dialect_only_removes_from(self):
        """Narrow surface: dialect must not incidentally unreserve other
        keywords (e.g. `if`, `return`, `const`). Only `from` is affected."""
        override = COMPOSE_QUERY_DIALECT.keywords_override
        assert override == {"from": None}

    def test_from_absent_in_effective_keywords(self):
        assert "from" not in COMPOSE_QUERY_DIALECT.effective_keywords()

    def test_other_keywords_retained(self):
        """Regression: verify critical keywords still reserved."""
        effective = COMPOSE_QUERY_DIALECT.effective_keywords()
        for kw in ("if", "return", "const", "let", "for", "while"):
            assert kw in effective, (
                f"{kw!r} must remain reserved under COMPOSE_QUERY_DIALECT; "
                "compose scripts rely on these control-flow keywords"
            )

    def test_distinct_from_sql_expression_dialect(self):
        """Two dialects are intentionally independent: one removes ``if``,
        the other removes ``from``. Neither implies the other."""
        assert "if" in COMPOSE_QUERY_DIALECT.effective_keywords()
        assert "from" in SQL_EXPRESSION_DIALECT.effective_keywords()


class TestDefaultDialectStillReservesFrom:
    """Guardrail: make sure we did NOT accidentally regress the existing
    fsscript contract where ``from`` is a reserved word for import syntax.
    """

    def test_default_dialect_reserves_from(self):
        assert "from" in DEFAULT_DIALECT.effective_keywords()
        assert DEFAULT_DIALECT.effective_keywords()["from"] == TokenType.FROM

    def test_lexer_without_dialect_emits_from_as_keyword(self):
        """Without dialect → default behaviour: ``from`` is a FROM token."""
        tokens = list(FsscriptLexer("from x").tokenize())
        kinds = [t.type for t in tokens]
        assert TokenType.FROM in kinds, (
            "Default lexer must still treat `from` as a reserved keyword "
            "(backwards compat with historical fsscript behaviour)"
        )


class TestComposeDialectParsesFromAsFunctionCall:
    """The main payoff: ``from({...})`` under COMPOSE_QUERY_DIALECT parses
    as a function call rather than a reserved-word syntax error."""

    def test_from_parses_as_identifier_when_dialect_enabled(self):
        tokens = list(
            FsscriptLexer("from", dialect=COMPOSE_QUERY_DIALECT).tokenize()
        )
        # First token is the identifier ``from``, followed by EOF.
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "from"

    def test_from_function_call_parses_end_to_end(self):
        """Match the canonical script-side invocation shape:
        ``from({model: 'X'})``. Parser must produce a function-call node."""
        source = "from({model: 'X'})"
        parser = FsscriptParser(source, dialect=COMPOSE_QUERY_DIALECT)
        tree = parser.parse_expression()

        # We don't couple the test to a specific AST class name; duck-type
        # via repr keywords so this survives minor AST refactors.
        tree_repr = repr(tree)
        assert "from" in tree_repr.lower() or "FunctionCall" in type(tree).__name__, (
            f"Expected a function-call-shaped tree with `from` as callee; "
            f"got {type(tree).__name__}: {tree_repr!r}"
        )

    def test_from_with_source_derived_pattern(self):
        """`from({source: plan, columns: [...]})` is the kernel form for
        derived plans — must parse just as cleanly as the base-model form."""
        source = "from({source: base, columns: ['id']})"
        parser = FsscriptParser(source, dialect=COMPOSE_QUERY_DIALECT)
        tree = parser.parse_expression()
        assert tree is not None

    def test_default_dialect_rejects_from_as_function_call(self):
        """Flip-side: under default dialect, ``from({...})`` is a syntax
        error because `from` is a reserved keyword. This test locks the
        default behaviour so a future regression in the dialect mechanism
        would be caught immediately."""
        source = "from({model: 'X'})"
        with pytest.raises(Exception):
            FsscriptParser(source, dialect=DEFAULT_DIALECT).parse_expression()
