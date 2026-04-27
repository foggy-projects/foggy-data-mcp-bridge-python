"""G5 Phase 2 (F5) · Python parity for ``column_normalizer`` plan-qualified
column normalization + ``QueryPlan.collect_visible_plans()`` contract.

Mirrors Java's ``ColumnObjectNormalizerF5Test`` and
``QueryPlanVisibilityTest``. Python's plan IR is strictly
``Tuple[str, ...]`` so F5 Map syntax flattens to the same string form
as F4; the ``plan`` reference is validated at parse time and discarded
(see ``column_normalizer.py`` module docstring "Architectural divergence
from Java" for full rationale).
"""

from __future__ import annotations

from typing import List

import pytest

from foggy.dataset_model.engine.compose.plan.column_normalizer import (
    ALLOWED_F4_KEYS,
    ALLOWED_F5_KEYS,
    normalize,
    normalize_columns,
    normalize_columns_to_strings,
)
from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinOn,
    JoinPlan,
    PlanColumnRef,
    UnionPlan,
)


def _base(model: str, columns: List[str] = None) -> BaseModelPlan:
    return BaseModelPlan(model=model, columns=tuple(columns or ["id"]))


# ---------------------------------------------------------------------------
# F5 normalize · happy path (flatten to string equivalent of F4)
# ---------------------------------------------------------------------------


class TestF5HappyPath:
    def test_minimal_f5_returns_string_field(self):
        sales = _base("FactSalesQM")
        out = normalize({"plan": sales, "field": "amount"}, 0)
        assert out == "amount"

    def test_f5_with_agg_returns_aggregate_string(self):
        sales = _base("FactSalesQM")
        out = normalize({"plan": sales, "field": "amount", "agg": "sum"}, 0)
        assert out == "SUM(amount)"

    def test_f5_with_as_returns_aliased_string(self):
        sales = _base("FactSalesQM")
        out = normalize({"plan": sales, "field": "name", "as": "salesName"}, 0)
        assert out == "name AS salesName"

    def test_f5_with_agg_and_as_returns_compound_string(self):
        sales = _base("FactSalesQM")
        out = normalize({"plan": sales, "field": "amount", "agg": "sum", "as": "total"}, 0)
        assert out == "SUM(amount) AS total"

    def test_f5_count_distinct_uppercased(self):
        sales = _base("FactSalesQM")
        out = normalize({"plan": sales, "field": "customerId", "agg": "count_distinct"}, 0)
        # Engine lowering AllowedFunctions/SqlFunctionExp turns COUNT_DISTINCT(...)
        # into COUNT(DISTINCT ...) at SQL emission time — same path as F4.
        assert out == "COUNT_DISTINCT(customerId)"

    def test_f5_in_mixed_array_with_f1_f4(self):
        sales = _base("FactSalesQM")
        out = normalize_columns([
            "product$id",  # F1
            {"field": "orderDate", "as": "od"},  # F4
            {"plan": sales, "field": "amount", "agg": "sum", "as": "total"},  # F5
        ])
        assert out == ["product$id", "orderDate AS od", "SUM(amount) AS total"]


# ---------------------------------------------------------------------------
# F5 normalize · validation
# ---------------------------------------------------------------------------


class TestF5Validation:
    def test_plan_not_query_plan_type(self):
        # `plan` value is a string instead of a QueryPlan instance
        with pytest.raises(ValueError) as ei:
            normalize({"plan": "FactSalesQM", "field": "amount"}, 7)
        assert ei.value.args[0].startswith("COLUMN_PLAN_TYPE_INVALID:")
        assert "columns[7]" in ei.value.args[0]

    def test_f5_unknown_key_uses_f5_whitelist(self):
        sales = _base("FactSalesQM")
        with pytest.raises(ValueError) as ei:
            normalize({"plan": sales, "field": "amount", "foo": "bar"}, 0)
        assert ei.value.args[0].startswith("COLUMN_FIELD_INVALID_KEY:")
        # F5 whitelist mentions plan
        assert "plan" in ei.value.args[0]

    def test_f5_missing_field(self):
        sales = _base("FactSalesQM")
        with pytest.raises(ValueError) as ei:
            normalize({"plan": sales}, 0)
        assert ei.value.args[0].startswith("COLUMN_FIELD_REQUIRED:")

    def test_f5_invalid_agg(self):
        sales = _base("FactSalesQM")
        with pytest.raises(ValueError) as ei:
            normalize({"plan": sales, "field": "amount", "agg": "median"}, 0)
        assert ei.value.args[0].startswith("COLUMN_AGG_NOT_SUPPORTED:")

    def test_f5_non_string_as(self):
        sales = _base("FactSalesQM")
        with pytest.raises(ValueError) as ei:
            normalize({"plan": sales, "field": "amount", "as": 42}, 0)
        assert ei.value.args[0].startswith("COLUMN_AS_TYPE_INVALID:")

    def test_allowed_keys_constants_distinct(self):
        # Sanity — F4/F5 whitelists differ only by "plan"
        assert ALLOWED_F5_KEYS - ALLOWED_F4_KEYS == {"plan"}


# ---------------------------------------------------------------------------
# normalize_columns_to_strings F5 rejection (G5 spec §10.3 item 5)
# ---------------------------------------------------------------------------


class TestLegacyStringPathRejection:
    def test_chained_plan_column_ref_rejected(self):
        sales = _base("FactSalesQM")
        chained = PlanColumnRef(plan=sales, name="amount")
        with pytest.raises(ValueError) as ei:
            normalize_columns_to_strings([chained])
        assert ei.value.args[0].startswith("COLUMN_PLAN_TYPE_INVALID:")

    def test_f4_and_strings_still_work(self):
        out = normalize_columns_to_strings([
            "product$id",
            "name AS customer",
            {"field": "amount", "agg": "sum", "as": "total"},
        ])
        assert out == ["product$id", "name AS customer", "SUM(amount) AS total"]

    def test_f5_dict_flattens_through_legacy_path(self):
        # F5 dict flattens to string at parse stage, so legacy path
        # accepts it (parity with F4 dict).
        sales = _base("FactSalesQM")
        out = normalize_columns_to_strings([
            {"plan": sales, "field": "amount", "agg": "sum", "as": "total"},
        ])
        assert out == ["SUM(amount) AS total"]


# ---------------------------------------------------------------------------
# QueryPlan.collect_visible_plans contract
# ---------------------------------------------------------------------------


class TestCollectVisiblePlans:
    def test_base_leaf(self):
        base = _base("X")
        visible = base.collect_visible_plans()
        assert len(visible) == 1
        assert visible[0] is base

    def test_derived_includes_self_and_source(self):
        base = _base("X")
        derived = DerivedQueryPlan(source=base, columns=("id",))
        visible = derived.collect_visible_plans()
        assert len(visible) == 2
        assert any(p is derived for p in visible)
        assert any(p is base for p in visible)

    def test_join_includes_self_and_both_branches(self):
        a = _base("A")
        b = _base("B")
        join = JoinPlan(left=a, right=b, type="inner",
                        on=(JoinOn(left="id", op="=", right="id"),))
        visible = join.collect_visible_plans()
        assert len(visible) == 3
        assert any(p is join for p in visible)
        assert any(p is a for p in visible)
        assert any(p is b for p in visible)

    def test_union_includes_self_and_both_branches(self):
        a = _base("A")
        b = _base("B")
        union = UnionPlan(left=a, right=b, all=True)
        visible = union.collect_visible_plans()
        assert len(visible) == 3
        assert any(p is union for p in visible)
        assert any(p is a for p in visible)
        assert any(p is b for p in visible)

    def test_deeply_nested_derived_sees_all_subtree(self):
        a = _base("A")
        b = _base("B")
        join = JoinPlan(left=a, right=b, type="inner",
                        on=(JoinOn(left="id", op="=", right="id"),))
        derived = DerivedQueryPlan(source=join, columns=("id",))

        visible = derived.collect_visible_plans()
        # derived + join + a + b
        assert len(visible) == 4
        assert any(p is derived for p in visible)
        assert any(p is join for p in visible)
        assert any(p is a for p in visible)
        assert any(p is b for p in visible)

    def test_identity_keyed_same_model_two_instances_distinct(self):
        # G5 spec §5.1: same model name dsl()'d twice yields two distinct
        # instances NOT interchangeable — identity comparison required.
        a1 = _base("X")
        a2 = _base("X")
        assert a1 == a2  # value-equal under frozen dataclass
        assert a1 is not a2  # but distinct identity

        join = JoinPlan(left=a1, right=a2, type="inner",
                        on=(JoinOn(left="id", op="=", right="id"),))
        visible = join.collect_visible_plans()
        # join + a1 + a2 — 3 distinct instances
        assert len(visible) == 3
        # Verify both a1 and a2 are in the visible set by identity, not equality
        assert any(p is a1 for p in visible)
        assert any(p is a2 for p in visible)
