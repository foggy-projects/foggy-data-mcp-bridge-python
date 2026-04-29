"""S7a POC · ColumnSpec semantic metadata fields."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.relation.constants import (
    ReferencePolicy,
    SemanticKind,
)
from foggy.dataset_model.engine.compose.schema.output_schema import (
    ColumnSpec,
    OutputSchema,
)


class TestMetadataDefaults:
    def test_new_fields_default_to_none(self):
        cs = ColumnSpec(name="salesAmount", expression="salesAmount")
        assert cs.semantic_kind is None
        assert cs.value_meaning is None
        assert cs.lineage is None
        assert cs.reference_policy is None

    def test_fields_can_be_set(self):
        cs = ColumnSpec(
            name="ratio",
            expression="ratio",
            semantic_kind=SemanticKind.TIME_WINDOW_DERIVED,
            value_meaning="current relative to prior salesAmount",
            lineage=frozenset({"salesAmount"}),
            reference_policy=frozenset({ReferencePolicy.READABLE, ReferencePolicy.ORDERABLE}),
        )
        assert cs.semantic_kind == SemanticKind.TIME_WINDOW_DERIVED
        assert cs.value_meaning == "current relative to prior salesAmount"
        assert cs.lineage == frozenset({"salesAmount"})
        assert ReferencePolicy.READABLE in cs.reference_policy
        assert ReferencePolicy.ORDERABLE in cs.reference_policy
        assert ReferencePolicy.AGGREGATABLE not in cs.reference_policy


class TestEqualityUnchanged:
    def test_equals_ignores_metadata(self):
        base = ColumnSpec(name="col", expression="col")
        with_meta = ColumnSpec(
            name="col",
            expression="col",
            semantic_kind=SemanticKind.AGGREGATE_MEASURE,
            value_meaning="total sales",
            lineage=frozenset({"salesAmount"}),
            reference_policy=ReferencePolicy.MEASURE_DEFAULT,
        )
        assert base == with_meta

    def test_hash_ignores_metadata(self):
        base = ColumnSpec(name="col", expression="col")
        with_meta = ColumnSpec(
            name="col",
            expression="col",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        )
        assert hash(base) == hash(with_meta)

    def test_different_metadata_still_equal(self):
        a = ColumnSpec(
            name="x", expression="x",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        )
        b = ColumnSpec(
            name="x", expression="x",
            semantic_kind=SemanticKind.AGGREGATE_MEASURE,
            reference_policy=ReferencePolicy.MEASURE_DEFAULT,
        )
        assert a == b

    def test_windowable_metadata_still_equal(self):
        base = ColumnSpec(name="salesAmount", expression="salesAmount")
        with_windowable = ColumnSpec(
            name="salesAmount",
            expression="salesAmount",
            semantic_kind=SemanticKind.AGGREGATE_MEASURE,
            reference_policy=ReferencePolicy.MEASURE_DEFAULT,
        )
        assert ReferencePolicy.WINDOWABLE in with_windowable.reference_policy
        assert base == with_windowable
        assert hash(base) == hash(with_windowable)


class TestOutputSchemaWithMetadata:
    def test_schema_accepts_columns_with_metadata(self):
        cs1 = ColumnSpec(
            name="dim1", expression="dim1",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        )
        cs2 = ColumnSpec(
            name="measure1", expression="measure1",
            semantic_kind=SemanticKind.AGGREGATE_MEASURE,
            reference_policy=ReferencePolicy.MEASURE_DEFAULT,
        )
        schema = OutputSchema.of([cs1, cs2])
        assert len(schema) == 2
        assert schema.get("dim1").semantic_kind == SemanticKind.BASE_FIELD

    def test_frozen_metadata_preserved(self):
        cs = ColumnSpec(
            name="x", expression="x",
            lineage=frozenset({"a", "b"}),
        )
        assert "a" in cs.lineage
        assert "b" in cs.lineage
