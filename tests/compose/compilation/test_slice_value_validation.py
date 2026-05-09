"""Compiler preflight coverage for unsupported compose slice values."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import compile_plan_to_sql
from foggy.dataset_model.engine.compose.plan import BaseModelPlan, from_, subquery


ERROR_CODE = "COMPOSE_SLICE_VALUE_UNSUPPORTED"
SUBQUERY_ERROR_CODE = "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED"


def test_base_slice_query_plan_value_compiles_to_subquery(svc, ctx):
    """Phase 2: base slice subquery values now compile to SQL subqueries."""
    prior = BaseModelPlan(model="FactSalesModel", columns=("orderStatus$caption",))
    plan = BaseModelPlan(
        model="FactSalesModel",
        columns=("orderStatus$caption",),
        slice_=(
            {
                "field": "orderStatus$caption",
                "op": "not in",
                "value": prior,
            },
        ),
    )

    composed = compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="postgres")

    assert "NOT IN (SELECT " in composed.sql
    assert "IS NOT NULL)" in composed.sql
    assert "unhashable type" not in composed.sql


def test_in_list_scalar_values_still_compile(svc, ctx):
    plan = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption"],
    ).query(
        columns=["orderStatus$caption"],
        slice=[
            {
                "field": "orderStatus$caption",
                "op": "in",
                "value": ["draft", "done"],
            }
        ],
    )

    composed = compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="postgres")

    assert " IN (?, ?)" in composed.sql
    assert composed.params[-2:] == ["draft", "done"]


@pytest.mark.parametrize("op", ["in", "not in"])
def test_derived_slice_query_plan_value_lowers_to_sql_subquery(svc, ctx, op):
    prior = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption"],
        slice=[{"field": "salesAmount", "op": ">", "value": 100}],
        distinct=True,
    )
    current = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )
    plan = current.query(
        columns=["orderStatus$caption", "salesAmount"],
        slice=[
            {
                "field": "orderStatus$caption",
                "op": op,
                "value": prior,
            }
        ],
    )

    composed = compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="postgres")

    assert f" {_sql_op(op)} (SELECT " in composed.sql
    assert "WHERE cte_" in composed.sql
    assert "IS NOT NULL)" in composed.sql
    assert 100 in composed.params
    assert "unhashable type" not in composed.sql


def test_derived_slice_explicit_subquery_field_lowers_multi_column_plan(svc, ctx):
    prior = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )
    current = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )
    plan = current.query(
        columns=["orderStatus$caption", "salesAmount"],
        slice=[
            {
                "field": "orderStatus$caption",
                "op": "not in",
                "value": subquery(prior, "orderStatus$caption"),
            }
        ],
    )

    composed = compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="postgres")

    assert " NOT IN (SELECT " in composed.sql
    assert '"orderStatus$caption"' in composed.sql
    assert "IS NOT NULL)" in composed.sql


def test_derived_slice_implicit_multi_column_plan_requires_subquery_field(svc, ctx):
    prior = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )
    current = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )
    plan = current.query(
        columns=["orderStatus$caption", "salesAmount"],
        slice=[
            {
                "field": "orderStatus$caption",
                "op": "in",
                "value": prior,
            }
        ],
    )

    with pytest.raises(Exception) as exc_info:
        compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="postgres")

    message = str(exc_info.value)
    assert "COMPOSE_SUBQUERY_FIELD_AMBIGUOUS" in message
    assert "unhashable type" not in message


def test_derived_slice_subquery_field_must_exist(svc, ctx):
    prior = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption"],
    )
    current = from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )
    plan = current.query(
        columns=["orderStatus$caption", "salesAmount"],
        slice=[
            {
                "field": "orderStatus$caption",
                "op": "in",
                "value": subquery(prior, "missing"),
            }
        ],
    )

    with pytest.raises(Exception) as exc_info:
        compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="postgres")

    message = str(exc_info.value)
    assert "COMPOSE_SUBQUERY_FIELD_NOT_FOUND" in message
    assert "unhashable type" not in message


def _sql_op(op: str) -> str:
    return " ".join(op.upper().split())
