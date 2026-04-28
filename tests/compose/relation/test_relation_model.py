"""S7a POC · Relation model invariants."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.relation import (
    CompiledRelation,
    CteItem,
    RelationCapabilities,
    RelationSql,
)
from foggy.dataset_model.engine.compose.relation.constants import (
    ReferencePolicy,
    RelationPermissionState,
    RelationWrapStrategy,
    SemanticKind,
)
from foggy.dataset_model.engine.compose.schema.output_schema import (
    ColumnSpec,
    OutputSchema,
)


def _sample_schema() -> OutputSchema:
    return OutputSchema.of([
        ColumnSpec(
            name="storeName", expression="storeName",
            semantic_kind=SemanticKind.BASE_FIELD,
            reference_policy=ReferencePolicy.DIMENSION_DEFAULT,
        ),
        ColumnSpec(
            name="salesAmount", expression="salesAmount",
            semantic_kind=SemanticKind.AGGREGATE_MEASURE,
            reference_policy=ReferencePolicy.MEASURE_DEFAULT,
        ),
    ])


class TestCteItem:
    def test_valid_construction(self):
        item = CteItem(name="cte_0", sql="SELECT 1")
        assert item.name == "cte_0"
        assert item.params == ()
        assert not item.recursive

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError):
            CteItem(name="", sql="SELECT 1")

    def test_rejects_empty_sql(self):
        with pytest.raises(ValueError):
            CteItem(name="x", sql="")


class TestRelationSql:
    def test_basic_construction(self):
        rsql = RelationSql(body_sql="SELECT 1", preferred_alias="rel_0")
        assert not rsql.contains_with_items
        assert rsql.flatten_params() == ()

    def test_flatten_params_order(self):
        cte0 = CteItem(name="__rel0_tw_base", sql="SELECT * FROM t WHERE d >= ?",
                        params=("2024-01-01",))
        cte1 = CteItem(name="__rel0_tw_prior", sql="SELECT * FROM t WHERE d >= ?",
                        params=("2023-01-01",))
        rsql = RelationSql(
            body_sql="SELECT * FROM __rel0_tw_base JOIN __rel0_tw_prior",
            preferred_alias="rel_0",
            with_items=(cte0, cte1),
            body_params=("body_param",),
        )
        assert rsql.flatten_params() == ("2024-01-01", "2023-01-01", "body_param")
        assert rsql.contains_with_items

    def test_rejects_empty_body(self):
        with pytest.raises(ValueError):
            RelationSql(body_sql="", preferred_alias="rel_0")


class TestRelationCapabilities:
    @pytest.mark.parametrize("dialect", ["mysql8", "postgres", "sqlite"])
    def test_cte_capable_with_cte(self, dialect):
        caps = RelationCapabilities.for_dialect(dialect, True)
        assert caps.relation_wrap_strategy == RelationWrapStrategy.HOISTED_CTE
        assert caps.can_hoist_cte
        assert caps.contains_with_items
        assert not caps.can_inline_as_subquery

    @pytest.mark.parametrize("dialect", [
        "mysql8", "postgres", "sqlite", "mssql", "sqlserver", "mysql", "mysql57",
    ])
    def test_no_cte_always_inline(self, dialect):
        caps = RelationCapabilities.for_dialect(dialect, False)
        assert caps.relation_wrap_strategy == RelationWrapStrategy.INLINE_SUBQUERY
        assert caps.can_inline_as_subquery
        assert not caps.contains_with_items

    @pytest.mark.parametrize("dialect", ["mssql", "sqlserver"])
    def test_sql_server_with_cte(self, dialect):
        caps = RelationCapabilities.for_dialect(dialect, True)
        assert caps.relation_wrap_strategy == RelationWrapStrategy.HOISTED_CTE
        assert caps.requires_top_level_with
        assert caps.can_hoist_cte
        assert not caps.can_inline_as_subquery

    @pytest.mark.parametrize("dialect", ["mysql", "mysql57"])
    def test_mysql57_with_cte_fail_closed(self, dialect):
        caps = RelationCapabilities.for_dialect(dialect, True)
        assert caps.relation_wrap_strategy == RelationWrapStrategy.FAIL_CLOSED
        assert not caps.can_hoist_cte
        assert not caps.can_inline_as_subquery

    def test_outer_capabilities_not_opened(self):
        for d in ("mysql8", "postgres", "sqlite", "mssql", "mysql"):
            for has_cte in (True, False):
                caps = RelationCapabilities.for_dialect(d, has_cte)
                assert not caps.supports_outer_aggregate, \
                    f"S7a must not open outer aggregate for {d}"
                assert not caps.supports_outer_window, \
                    f"S7a must not open outer window for {d}"


class TestCompiledRelation:
    def test_builder_produces_valid_instance(self):
        rsql = RelationSql(
            body_sql="SELECT storeName, SUM(amount) FROM fact_sales GROUP BY storeName",
            preferred_alias="rel_0",
        )
        rel = CompiledRelation(
            alias="rel_0",
            relation_sql=rsql,
            output_schema=_sample_schema(),
            datasource_id="demo",
            dialect="mysql8",
            capabilities=RelationCapabilities.for_dialect("mysql8", False),
            permission_state=RelationPermissionState.UNKNOWN,
        )
        assert rel.alias == "rel_0"
        assert rel.datasource_id == "demo"
        assert rel.dialect == "mysql8"
        assert rel.permission_state == RelationPermissionState.UNKNOWN
        assert len(rel.output_schema) == 2

    def test_rejects_empty_alias(self):
        rsql = RelationSql(body_sql="SELECT 1", preferred_alias="rel_0")
        with pytest.raises(ValueError):
            CompiledRelation(
                alias="",
                relation_sql=rsql,
                output_schema=_sample_schema(),
                dialect="mysql8",
                capabilities=RelationCapabilities.for_dialect("mysql8", False),
            )


class TestConstants:
    def test_semantic_kind(self):
        assert len(SemanticKind.ALL) == 5
        assert SemanticKind.is_valid(SemanticKind.BASE_FIELD)
        assert not SemanticKind.is_valid("unknown")

    def test_reference_policy(self):
        assert len(ReferencePolicy.ALL) == 5
        assert ReferencePolicy.is_valid(ReferencePolicy.READABLE)

    def test_wrap_strategy(self):
        assert len(RelationWrapStrategy.ALL) == 4
        assert RelationWrapStrategy.is_valid(RelationWrapStrategy.HOISTED_CTE)

    def test_permission_state(self):
        assert len(RelationPermissionState.ALL) == 3
        assert RelationPermissionState.is_valid(RelationPermissionState.UNKNOWN)
