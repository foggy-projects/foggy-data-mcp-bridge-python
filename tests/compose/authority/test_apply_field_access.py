"""M5 ``apply_field_access_to_schema`` — OutputSchema filter by
``ModelBinding.field_access``.

Covers:
    * field_access=None → no-op (returns input schema unchanged)
    * field_access=[] → empty schema (explicit "no visible field")
    * field_access=[names] → whitelist filter, preserves original order
    * field_access with names absent from schema → ignored (no error)
    * Duplicate whitelist entries → harmless
    * TypeError on None / wrong-type inputs
    * deniedColumns / system_slice untouched (only field_access matters here)
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.authority import (
    apply_field_access_to_schema,
)
from foggy.dataset_model.engine.compose.schema import ColumnSpec, OutputSchema
from foggy.dataset_model.engine.compose.security import ModelBinding
from foggy.mcp_spi.semantic import DeniedColumn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schema_abc() -> OutputSchema:
    return OutputSchema.of(
        [
            ColumnSpec(name="a", expression="a"),
            ColumnSpec(name="b", expression="b"),
            ColumnSpec(name="c", expression="c"),
        ]
    )


# ---------------------------------------------------------------------------
# field_access = None → no-op
# ---------------------------------------------------------------------------


class TestFieldAccessNone:
    def test_returns_input_unchanged(self):
        schema = _schema_abc()
        binding = ModelBinding()  # field_access defaults to None
        result = apply_field_access_to_schema(schema, binding)
        assert result is schema

    def test_explicit_none_same_as_default(self):
        schema = _schema_abc()
        binding = ModelBinding(field_access=None)
        result = apply_field_access_to_schema(schema, binding)
        assert result is schema


# ---------------------------------------------------------------------------
# field_access = [] → empty schema
# ---------------------------------------------------------------------------


class TestFieldAccessEmpty:
    def test_empty_list_strips_all_columns(self):
        schema = _schema_abc()
        binding = ModelBinding(field_access=[])
        result = apply_field_access_to_schema(schema, binding)
        assert isinstance(result, OutputSchema)
        assert len(result) == 0

    def test_empty_list_is_not_identity(self):
        """Empty != None: returns a fresh empty schema, not the input."""
        schema = _schema_abc()
        binding = ModelBinding(field_access=[])
        result = apply_field_access_to_schema(schema, binding)
        assert result is not schema


# ---------------------------------------------------------------------------
# Whitelist filtering
# ---------------------------------------------------------------------------


class TestWhitelist:
    def test_keeps_only_matching_columns(self):
        schema = _schema_abc()
        binding = ModelBinding(field_access=["a", "c"])
        result = apply_field_access_to_schema(schema, binding)
        assert result.names() == ["a", "c"]

    def test_preserves_original_order(self):
        schema = _schema_abc()
        # Whitelist in reverse; output should still be a,b order from schema.
        binding = ModelBinding(field_access=["c", "a"])
        result = apply_field_access_to_schema(schema, binding)
        assert result.names() == ["a", "c"]

    def test_unknown_names_are_silently_ignored(self):
        schema = _schema_abc()
        binding = ModelBinding(field_access=["a", "phantom"])
        result = apply_field_access_to_schema(schema, binding)
        assert result.names() == ["a"]

    def test_duplicate_whitelist_entries_harmless(self):
        schema = _schema_abc()
        binding = ModelBinding(field_access=["a", "a", "b"])
        result = apply_field_access_to_schema(schema, binding)
        assert result.names() == ["a", "b"]

    def test_column_spec_carried_over_intact(self):
        """The filter preserves the full ColumnSpec (expression, source, etc.)."""
        schema = OutputSchema.of(
            [
                ColumnSpec(
                    name="total",
                    expression="SUM(amount) AS total",
                    source_model="SaleOrderQM",
                    has_explicit_alias=True,
                ),
            ]
        )
        binding = ModelBinding(field_access=["total"])
        result = apply_field_access_to_schema(schema, binding)
        assert len(result) == 1
        kept = result.get("total")
        assert kept is not None
        assert kept.expression == "SUM(amount) AS total"
        assert kept.source_model == "SaleOrderQM"
        assert kept.has_explicit_alias is True


# ---------------------------------------------------------------------------
# Doesn't interact with denied_columns / system_slice
# ---------------------------------------------------------------------------


class TestIndependentOfOtherBindingFields:
    def test_denied_columns_ignored(self):
        """denied_columns is M6 scope; this helper leaves them untouched."""
        schema = _schema_abc()
        binding = ModelBinding(
            field_access=["a", "b"],
            denied_columns=[
                DeniedColumn(table="sale_order", column="a_phys"),
            ],
        )
        result = apply_field_access_to_schema(schema, binding)
        # Filter happens purely on field_access — denied_columns not
        # consulted at M5. ``a`` is in the whitelist, so it stays.
        assert result.names() == ["a", "b"]

    def test_system_slice_ignored(self):
        schema = _schema_abc()
        binding = ModelBinding(
            field_access=["b"],
            system_slice=[{"field": "user_id", "op": "=", "value": 1}],
        )
        result = apply_field_access_to_schema(schema, binding)
        assert result.names() == ["b"]


# ---------------------------------------------------------------------------
# Fail-closed on bad inputs
# ---------------------------------------------------------------------------


class TestBadInputs:
    def test_schema_none_raises(self):
        binding = ModelBinding(field_access=["a"])
        with pytest.raises(TypeError, match="schema must not be None"):
            apply_field_access_to_schema(None, binding)

    def test_schema_wrong_type_raises(self):
        binding = ModelBinding(field_access=["a"])
        with pytest.raises(TypeError, match="schema must be OutputSchema"):
            apply_field_access_to_schema("not a schema", binding)

    def test_binding_none_raises(self):
        schema = _schema_abc()
        with pytest.raises(TypeError, match="binding must not be None"):
            apply_field_access_to_schema(schema, None)

    def test_binding_wrong_type_raises(self):
        schema = _schema_abc()
        with pytest.raises(TypeError, match="binding must be ModelBinding"):
            apply_field_access_to_schema(schema, {"field_access": ["a"]})


# ---------------------------------------------------------------------------
# Empty input schema
# ---------------------------------------------------------------------------


class TestEmptyInputSchema:
    def test_empty_schema_with_whitelist_stays_empty(self):
        empty = OutputSchema.of([])
        binding = ModelBinding(field_access=["a", "b"])
        result = apply_field_access_to_schema(empty, binding)
        assert len(result) == 0

    def test_empty_schema_with_none_access_stays_empty(self):
        empty = OutputSchema.of([])
        binding = ModelBinding()
        result = apply_field_access_to_schema(empty, binding)
        assert len(result) == 0
