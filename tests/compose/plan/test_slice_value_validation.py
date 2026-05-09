"""Fail-closed validation for object-like compose slice values."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import from_, subquery


ERROR_CODE = "COMPOSE_SLICE_VALUE_UNSUPPORTED"
SUBQUERY_ERROR_CODE = "COMPOSE_SUBQUERY_VALUE_UNSUPPORTED"


def _base(columns=None):
    return from_(
        model="FactSalesModel",
        columns=columns or ["orderStatus$caption", "salesAmount"],
    )


class TestSliceValueValidation:
    @pytest.mark.parametrize("op", ["in", "not in"])
    def test_plan_query_allows_query_plan_slice_value_for_in_operators(self, op):
        prior = _base(["orderStatus$caption"])
        current = _base(["orderStatus$caption", "salesAmount"])

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

        assert plan.slice_[0]["value"] is prior

    @pytest.mark.parametrize("op", ["in", "not in"])
    def test_plan_query_allows_explicit_subquery_slice_value(self, op):
        prior = _base(["orderStatus$caption", "salesAmount"])
        current = _base(["orderStatus$caption", "salesAmount"])

        plan = current.query(
            columns=["orderStatus$caption", "salesAmount"],
            slice=[
                {
                    "field": "orderStatus$caption",
                    "op": op,
                    "value": subquery(prior, "orderStatus$caption"),
                }
            ],
        )

        assert plan.slice_[0]["value"].field == "orderStatus$caption"

    def test_plan_query_rejects_query_plan_slice_value_for_non_in_operator(self):
        prior = _base(["orderStatus$caption"])
        current = _base(["orderStatus$caption", "salesAmount"])

        with pytest.raises(ValueError) as exc_info:
            current.query(
                columns=["orderStatus$caption", "salesAmount"],
                slice=[
                    {
                        "field": "orderStatus$caption",
                        "op": "=",
                        "value": prior,
                    }
                ],
            )

        message = str(exc_info.value)
        assert SUBQUERY_ERROR_CODE in message
        assert "unhashable type" not in message

    @pytest.mark.parametrize("op", ["in", "not in"])
    def test_plan_query_rejects_object_slice_value(self, op):
        current = _base(["orderStatus$caption", "salesAmount"])

        with pytest.raises(ValueError) as exc_info:
            current.query(
                columns=["orderStatus$caption", "salesAmount"],
                slice=[
                    {
                        "field": "orderStatus$caption",
                        "op": op,
                        "value": {"nested": "value"},
                    }
                ],
            )

        assert ERROR_CODE in str(exc_info.value)
        assert "unhashable type" not in str(exc_info.value)

    @pytest.mark.parametrize("op", ["in", "not in"])
    def test_plan_query_rejects_object_inside_list_slice_value(self, op):
        current = _base(["orderStatus$caption", "salesAmount"])

        with pytest.raises(ValueError) as exc_info:
            current.query(
                columns=["orderStatus$caption", "salesAmount"],
                slice=[
                    {
                        "field": "orderStatus$caption",
                        "op": op,
                        "value": ["draft", {"nested": "value"}],
                    }
                ],
            )

        assert ERROR_CODE in str(exc_info.value)
        assert "unhashable type" not in str(exc_info.value)

    def test_base_dsl_rejects_object_slice_value(self):
        with pytest.raises(ValueError) as exc_info:
            from_(
                model="FactSalesModel",
                columns=["orderStatus$caption"],
                slice=[
                    {
                        "field": "orderStatus$caption",
                        "op": "=",
                        "value": {"nested": "value"},
                    }
                ],
            )

        assert ERROR_CODE in str(exc_info.value)
        assert "unhashable type" not in str(exc_info.value)

    def test_in_list_scalar_values_still_build(self):
        plan = _base(["orderStatus$caption"]).query(
            columns=["orderStatus$caption"],
            slice=[
                {
                    "field": "orderStatus$caption",
                    "op": "in",
                    "value": ["draft", "done"],
                }
            ],
        )

        assert plan.slice_[0]["value"] == ["draft", "done"]
