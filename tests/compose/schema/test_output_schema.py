"""M4 · ColumnSpec + OutputSchema frozen-dataclass invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.schema import ColumnSpec, OutputSchema


class TestColumnSpecInvariants:
    def test_minimal_valid_construction(self):
        c = ColumnSpec(name="orderId", expression="orderId")
        assert c.name == "orderId"
        assert c.expression == "orderId"
        assert c.source_model is None
        assert c.data_type is None
        assert c.has_explicit_alias is False

    def test_name_required_non_empty(self):
        with pytest.raises(ValueError):
            ColumnSpec(name="", expression="x")
        with pytest.raises(ValueError):
            ColumnSpec(name=None, expression="x")  # type: ignore[arg-type]

    def test_expression_required_non_empty(self):
        with pytest.raises(ValueError):
            ColumnSpec(name="x", expression="")

    def test_frozen(self):
        c = ColumnSpec(name="x", expression="x")
        with pytest.raises(Exception):
            c.name = "y"  # type: ignore[misc]

    def test_value_equality(self):
        a = ColumnSpec(name="x", expression="x", source_model="M")
        b = ColumnSpec(name="x", expression="x", source_model="M")
        assert a == b
        assert hash(a) == hash(b)


class TestOutputSchemaConstruction:
    def test_empty_schema_is_legal(self):
        s = OutputSchema()
        assert len(s) == 0
        assert list(s) == []
        assert s.names() == []

    def test_of_classmethod_normalises_to_tuple(self):
        s = OutputSchema.of([
            ColumnSpec(name="a", expression="a"),
            ColumnSpec(name="b", expression="b"),
        ])
        assert isinstance(s.columns, tuple)
        assert [c.name for c in s] == ["a", "b"]

    def test_duplicate_output_names_rejected(self):
        """Two columns with the same output name is a plan-level
        mistake that must surface early."""
        with pytest.raises(ValueError):
            OutputSchema.of([
                ColumnSpec(name="x", expression="a"),
                ColumnSpec(name="x", expression="b"),
            ])

    def test_columns_must_be_ColumnSpec(self):
        with pytest.raises(TypeError):
            OutputSchema.of([
                {"name": "x", "expression": "x"},  # type: ignore[list-item]
            ])


class TestOutputSchemaAccessors:
    def _three_col_schema(self) -> OutputSchema:
        return OutputSchema.of([
            ColumnSpec(name="id", expression="id"),
            ColumnSpec(name="name", expression="name"),
            ColumnSpec(name="total", expression="SUM(amount)",
                       has_explicit_alias=True),
        ])

    def test_names_returns_ordered_list(self):
        s = self._three_col_schema()
        assert s.names() == ["id", "name", "total"]

    def test_name_set_is_frozen(self):
        s = self._three_col_schema()
        assert s.name_set() == frozenset({"id", "name", "total"})

    def test_contains_and_get(self):
        s = self._three_col_schema()
        assert s.contains("id") is True
        assert s.contains("missing") is False
        assert s.get("total").expression == "SUM(amount)"
        assert s.get("missing") is None

    def test_index_of_hits_and_misses(self):
        s = self._three_col_schema()
        assert s.index_of("id") == 0
        assert s.index_of("total") == 2
        with pytest.raises(KeyError):
            s.index_of("missing")

    def test_iteration_order_matches_construction(self):
        s = self._three_col_schema()
        collected = [c.name for c in s]
        assert collected == ["id", "name", "total"]


class TestOutputSchemaImmutability:
    def test_frozen_attribute(self):
        s = OutputSchema.of([ColumnSpec(name="x", expression="x")])
        with pytest.raises(Exception):
            s.columns = ()  # type: ignore[misc]

    def test_value_equality_and_hash(self):
        a = OutputSchema.of([ColumnSpec(name="x", expression="x")])
        b = OutputSchema.of([ColumnSpec(name="x", expression="x")])
        assert a == b
        assert hash(a) == hash(b)
