"""M4 · extract_column_alias edge-case coverage."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.schema import extract_column_alias
from foggy.dataset_model.engine.compose.schema.alias import ColumnAliasParts


class TestBareColumnNames:
    def test_plain_identifier(self):
        parts = extract_column_alias("orderId")
        assert parts == ColumnAliasParts(
            expression="orderId", output_name="orderId", has_alias=False
        )

    def test_dimension_path(self):
        """`customer$id` is a valid bare output name."""
        parts = extract_column_alias("customer$id")
        assert parts.output_name == "customer$id"
        assert parts.has_alias is False

    def test_whitespace_is_stripped(self):
        parts = extract_column_alias("   orderId   ")
        assert parts.expression == "orderId"
        assert parts.output_name == "orderId"


class TestFunctionExpressions:
    def test_aggregate_without_alias_keeps_expression_as_output(self):
        parts = extract_column_alias("SUM(amount)")
        assert parts.expression == "SUM(amount)"
        assert parts.output_name == "SUM(amount)"
        assert parts.has_alias is False

    def test_nested_iif_expression(self):
        spec = "SUM(IIF(isOverdue==1, residualAmount, 0))"
        parts = extract_column_alias(spec)
        assert parts.output_name == spec
        assert parts.has_alias is False


class TestAliasExtraction:
    def test_uppercase_as(self):
        parts = extract_column_alias("orderId AS oid")
        assert parts.expression == "orderId"
        assert parts.output_name == "oid"
        assert parts.has_alias is True

    def test_lowercase_as(self):
        parts = extract_column_alias("orderId as oid")
        assert parts.output_name == "oid"

    def test_mixed_case_as(self):
        parts = extract_column_alias("orderId As oid")
        assert parts.output_name == "oid"

    def test_aggregate_with_alias(self):
        parts = extract_column_alias("SUM(amount) AS totalAmount")
        assert parts.expression == "SUM(amount)"
        assert parts.output_name == "totalAmount"

    def test_deeply_nested_with_alias(self):
        spec = "SUM(IIF(isOverdue == 1, residualAmount, 0)) AS customerOverdue"
        parts = extract_column_alias(spec)
        assert parts.expression == "SUM(IIF(isOverdue == 1, residualAmount, 0))"
        assert parts.output_name == "customerOverdue"

    def test_extra_whitespace_around_as(self):
        parts = extract_column_alias("   orderId   AS   oid   ")
        assert parts.expression == "orderId"
        assert parts.output_name == "oid"

    def test_dimension_path_alias(self):
        parts = extract_column_alias("customer$id AS customerId")
        assert parts.expression == "customer$id"
        assert parts.output_name == "customerId"


class TestAsInsideIdentifierNotMatched:
    """`ASSETS` / `CAST` etc. must NOT trigger alias extraction."""

    def test_as_substring_in_identifier(self):
        """`SUM(ASSETS)` has no whitespace around AS → not an alias split."""
        parts = extract_column_alias("SUM(ASSETS)")
        assert parts.output_name == "SUM(ASSETS)"
        assert parts.has_alias is False

    def test_as_inside_string_literal_does_not_split(self):
        """AS appearing inside a string literal is ignored by the scanner.

        Note: this works because the pattern requires whitespace on both
        sides of AS; the literal `' AS '` inside quotes does match the
        pattern, but the alias slot after it would fail identifier
        validation. We cover this case to document the behaviour."""
        parts = extract_column_alias("'foo AS bar'")
        # Whitespace-anchored AS does match inside the literal, but the
        # trailing slot `bar'` is not a legal identifier → falls back to
        # treating the whole input as expression.
        assert parts.has_alias is False
        assert parts.output_name == "'foo AS bar'"


class TestMalformedInputs:
    def test_non_string_rejected(self):
        with pytest.raises(TypeError):
            extract_column_alias(123)  # type: ignore[arg-type]

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            extract_column_alias("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError):
            extract_column_alias("   ")

    def test_leading_as_treated_as_expression(self):
        """Input `' AS alias'` after strip becomes `'AS alias'`; the
        `\\s+AS\\s+` pattern requires whitespace before AS so no match,
        and the whole string becomes the expression. This is defensible
        safe-failure behaviour — downstream schema derivation will then
        raise an unknown-field error if `AS` resolves to nothing."""
        parts = extract_column_alias(" AS alias")
        assert parts.has_alias is False
        assert parts.expression == "AS alias"

    def test_alias_with_bad_identifier_falls_back_to_full_expression(self):
        """`x AS 1foo` — alias starts with a digit, not a legal ident."""
        parts = extract_column_alias("x AS 1foo")
        assert parts.has_alias is False
        assert parts.output_name == "x AS 1foo"
