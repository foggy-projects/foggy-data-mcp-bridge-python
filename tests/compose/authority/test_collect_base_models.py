"""M5 ``collect_base_models`` — tree walk + first-occurrence dedup.

Covers:
    * Single BaseModelPlan input
    * DerivedQueryPlan recursion
    * UnionPlan / JoinPlan left-right preorder
    * Dedup by ``.model`` string (not by ``BaseModelPlan`` identity)
    * TypeError fail-closed on non-QueryPlan input
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.authority import collect_base_models
from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    JoinPlan,
    QueryPlan,
    UnionPlan,
    from_,
)
from foggy.dataset_model.engine.compose.plan.plan import JoinOn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sale_order() -> BaseModelPlan:
    return from_(model="SaleOrderQM", columns=["id", "amount"])


def _crm_lead() -> BaseModelPlan:
    return from_(model="CrmLeadQM", columns=["id", "partner_id"])


def _partner() -> BaseModelPlan:
    return from_(model="ResPartnerQM", columns=["id", "name"])


# ---------------------------------------------------------------------------
# Basic traversal
# ---------------------------------------------------------------------------


class TestCollectFromBaseModel:
    def test_single_base_model_returns_itself(self):
        bp = _sale_order()
        result = collect_base_models(bp)
        assert result == [bp]

    def test_derived_recurses_to_source(self):
        bp = _sale_order()
        derived = bp.query(columns=["id", "amount"])
        result = collect_base_models(derived)
        assert [r.model for r in result] == ["SaleOrderQM"]
        # The returned BaseModelPlan is the one at the leaf, not the derived.
        assert result[0] is bp


class TestCollectFromUnion:
    def test_union_preserves_left_right_order(self):
        left = _sale_order()
        right = _crm_lead()
        union = left.union(right)
        result = collect_base_models(union)
        assert [r.model for r in result] == ["SaleOrderQM", "CrmLeadQM"]

    def test_union_with_same_model_on_both_sides_dedups(self):
        """Two ``from_('SaleOrderQM', ...)`` instances in a union resolve to
        one binding — the authority lifecycle is per QM, not per call site."""
        left = _sale_order()
        right = from_(model="SaleOrderQM", columns=["id"])  # different columns
        union = left.union(right)
        result = collect_base_models(union)
        assert [r.model for r in result] == ["SaleOrderQM"]
        # First-occurrence wins: the returned plan is the left leaf.
        assert result[0] is left


class TestCollectFromJoin:
    def test_join_preserves_left_right_order(self):
        left = _sale_order()
        right = _partner()
        joined = left.join(
            right,
            type="inner",
            on=[JoinOn(left="partner_id", op="=", right="id")],
        )
        result = collect_base_models(joined)
        assert [r.model for r in result] == ["SaleOrderQM", "ResPartnerQM"]


class TestCollectFromDeepTree:
    def test_derived_of_union_of_join(self):
        sale = _sale_order()
        crm = _crm_lead()
        partner = _partner()

        joined = sale.join(
            partner,
            type="left",
            on=[JoinOn(left="partner_id", op="=", right="id")],
        )
        union = joined.union(crm)
        top = union.query(columns=["id"])

        result = collect_base_models(top)
        assert [r.model for r in result] == [
            "SaleOrderQM",
            "ResPartnerQM",
            "CrmLeadQM",
        ]

    def test_dedup_across_branches(self):
        """Same QM appears in the left arm of a join and in a union — one
        binding is enough."""
        sale_a = _sale_order()
        sale_b = from_(model="SaleOrderQM", columns=["id"])
        partner = _partner()
        joined = sale_a.join(
            partner,
            type="left",
            on=[JoinOn(left="partner_id", op="=", right="id")],
        )
        unioned = joined.union(sale_b)
        result = collect_base_models(unioned)
        assert [r.model for r in result] == ["SaleOrderQM", "ResPartnerQM"]
        # First-occurrence wins: sale_a survives, sale_b drops.
        assert result[0] is sale_a


# ---------------------------------------------------------------------------
# Fail-closed
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_non_plan_input_raises_type_error(self):
        with pytest.raises(TypeError, match="QueryPlan instance"):
            collect_base_models("not a plan")

    def test_none_input_raises_type_error(self):
        with pytest.raises(TypeError, match="QueryPlan instance"):
            collect_base_models(None)

    def test_subclass_leaking_non_base_model_is_rejected(self):
        """Defensive: if a QueryPlan subclass ever returns a non-BaseModelPlan
        from ``base_model_plans()``, collect refuses to proceed."""

        class Rogue(QueryPlan):
            def base_model_plans(self):  # type: ignore[override]
                return ("NOT A PLAN",)  # type: ignore[return-value]

            def collect_visible_plans(self):  # type: ignore[override]
                return (self,)

        with pytest.raises(TypeError, match="non-BaseModelPlan"):
            collect_base_models(Rogue())
