"""M4 · derive_schema per-plan-type behaviour."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    from_,
)
from foggy.dataset_model.engine.compose.plan.plan import JoinOn
from foggy.dataset_model.engine.compose.schema import (
    ColumnSpec,
    ComposeSchemaError,
    OutputSchema,
    derive_schema,
)
from foggy.dataset_model.engine.compose.schema import error_codes


# ---------------------------------------------------------------------------
# BaseModelPlan
# ---------------------------------------------------------------------------


class TestBaseModelSchema:
    def test_simple_column_list(self):
        plan = from_(model="SaleOrderQM", columns=["id", "name", "total"])
        schema = derive_schema(plan)
        assert schema.names() == ["id", "name", "total"]
        assert all(c.source_model == "SaleOrderQM" for c in schema)

    def test_alias_strips_expression_in_output_name(self):
        plan = from_(
            model="SaleOrderQM",
            columns=["SUM(amount) AS total", "customer$id AS customerId"],
        )
        schema = derive_schema(plan)
        assert schema.names() == ["total", "customerId"]
        assert schema.get("total").expression == "SUM(amount)"
        assert schema.get("total").has_explicit_alias is True
        assert schema.get("customerId").expression == "customer$id"

    def test_mixed_aliased_and_bare(self):
        plan = from_(
            model="X",
            columns=[
                "orderId",
                "SUM(amount) AS total",
                "COUNT(*) AS orderCount",
            ],
        )
        schema = derive_schema(plan)
        assert schema.names() == ["orderId", "total", "orderCount"]

    def test_duplicate_output_names_rejected_at_base(self):
        """Two columns aliased to same name — caught at derivation."""
        plan = from_(
            model="X", columns=["a AS x", "b AS x"],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(plan)
        assert exc_info.value.code == error_codes.DUPLICATE_OUTPUT_COLUMN
        assert exc_info.value.offending_field == "x"

    def test_derive_expects_queryplan_not_raw_data(self):
        with pytest.raises(TypeError):
            derive_schema("not a plan")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DerivedQueryPlan
# ---------------------------------------------------------------------------


class TestDerivedQuerySchema:
    def _base(self) -> BaseModelPlan:
        return from_(
            model="SaleOrderQM",
            columns=["orderId", "customer$id", "amount"],
        )

    def test_propagates_columns_from_source(self):
        base = self._base()
        derived = base.query(columns=["orderId"])
        schema = derive_schema(derived)
        assert schema.names() == ["orderId"]

    def test_references_unknown_field_rejected(self):
        base = self._base()
        derived = base.query(columns=["nonExistent"])
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(derived)
        err = exc_info.value
        assert err.code == error_codes.DERIVED_QUERY_UNKNOWN_FIELD
        assert err.offending_field == "nonExistent"
        assert "DerivedQueryPlan" in (err.plan_path or "")

    def test_aliased_output_reusable_by_further_derivation(self):
        """Alias-projected name is the reference target for the next layer."""
        base = from_(
            model="X", columns=["amount", "rate"],
        )
        level1 = base.query(columns=["amount * rate AS total"])
        level2 = level1.query(columns=["total"])  # <-- uses the alias
        schema = derive_schema(level2)
        assert schema.names() == ["total"]

    def test_derived_without_projection_hides_original_field(self):
        """Un-projected base fields must NOT be referenceable downstream."""
        base = from_(model="X", columns=["amount", "rate"])
        level1 = base.query(columns=["amount"])  # rate NOT projected
        # level2 tries to reference `rate` which is no longer visible
        level2 = level1.query(columns=["rate"])
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(level2)
        assert exc_info.value.code == error_codes.DERIVED_QUERY_UNKNOWN_FIELD
        assert exc_info.value.offending_field == "rate"

    def test_group_by_references_validated(self):
        base = from_(model="X", columns=["id", "amount"])
        derived = base.query(
            columns=["SUM(amount) AS total"], group_by=["missing"]
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(derived)
        assert exc_info.value.code == error_codes.DERIVED_QUERY_UNKNOWN_FIELD
        assert exc_info.value.offending_field == "missing"

    def test_order_by_desc_prefix_handled(self):
        """`-amount` is a desc-sort spec; the underlying field is validated."""
        base = from_(model="X", columns=["id", "amount"])
        derived = base.query(columns=["id", "amount"], order_by=["-amount"])
        # Should succeed — 'amount' is projected.
        schema = derive_schema(derived)
        assert schema.names() == ["id", "amount"]

    def test_reserved_tokens_in_expression_not_flagged(self):
        """`SUM` / `COALESCE` / `NULL` must not trigger unknown-field errors."""
        base = from_(model="X", columns=["amount", "discount"])
        derived = base.query(
            columns=["COALESCE(discount, 0) AS d", "SUM(amount) AS total"]
        )
        # Should succeed with no errors.
        schema = derive_schema(derived)
        assert schema.names() == ["d", "total"]


# ---------------------------------------------------------------------------
# UnionPlan
# ---------------------------------------------------------------------------


class TestUnionSchema:
    def test_matching_columns_succeeds(self):
        a = from_(model="CurrentQM", columns=["salespersonId", "amount"])
        b = from_(model="ArchivedQM", columns=["salespersonId", "amount"])
        schema = derive_schema(a.union(b, all=True))
        assert schema.names() == ["salespersonId", "amount"]

    def test_union_column_count_mismatch_rejected(self):
        a = from_(model="A", columns=["x", "y"])
        b = from_(model="B", columns=["x", "y", "z"])
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(a.union(b))
        err = exc_info.value
        assert err.code == error_codes.UNION_COLUMN_COUNT_MISMATCH
        assert "UnionPlan" in (err.plan_path or "")

    def test_union_output_names_come_from_left(self):
        """Right-side names are ignored; left defines the output shape."""
        a = from_(model="A", columns=["salesperson", "amount"])
        b = from_(model="B", columns=["who", "how_much"])
        schema = derive_schema(a.union(b))
        assert schema.names() == ["salesperson", "amount"]

    def test_union_of_derived_plans(self):
        base_a = from_(model="A", columns=["id", "amount"])
        base_b = from_(model="B", columns=["id", "amount"])
        derived_a = base_a.query(columns=["id", "amount AS amt"])
        derived_b = base_b.query(columns=["id", "amount AS amt"])
        schema = derive_schema(derived_a.union(derived_b))
        assert schema.names() == ["id", "amt"]


# ---------------------------------------------------------------------------
# JoinPlan
# ---------------------------------------------------------------------------


class TestJoinSchema:
    def test_join_preserves_both_sides_non_overlapping_columns(self):
        left = from_(
            model="SalesQM",
            columns=["partnerId", "totalSales"],
        )
        right = from_(
            model="LeadsQM",
            columns=["partnerKey", "leadCount"],
        )
        join = left.join(
            right,
            type="left",
            on=[JoinOn(left="partnerId", op="=", right="partnerKey")],
        )
        schema = derive_schema(join)
        assert schema.names() == [
            "partnerId", "totalSales", "partnerKey", "leadCount",
        ]

    def test_join_on_left_field_unknown_rejected(self):
        left = from_(model="A", columns=["x"])
        right = from_(model="B", columns=["y"])
        join = left.join(
            right,
            type="left",
            on=[JoinOn(left="missing", op="=", right="y")],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(join)
        assert exc_info.value.code == error_codes.JOIN_ON_LEFT_UNKNOWN_FIELD
        assert exc_info.value.offending_field == "missing"

    def test_join_on_right_field_unknown_rejected(self):
        left = from_(model="A", columns=["x"])
        right = from_(model="B", columns=["y"])
        join = left.join(
            right,
            type="left",
            on=[JoinOn(left="x", op="=", right="missing")],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(join)
        assert exc_info.value.code == error_codes.JOIN_ON_RIGHT_UNKNOWN_FIELD
        assert exc_info.value.offending_field == "missing"

    def test_join_output_column_conflict_rejected(self):
        """`partnerName` on both sides without disambiguation → error."""
        left = from_(
            model="A", columns=["partnerId", "partnerName", "totalSales"],
        )
        right = from_(
            model="B", columns=["partnerKey", "partnerName", "leadCount"],
        )
        join = left.join(
            right,
            type="left",
            on=[JoinOn(left="partnerId", op="=", right="partnerKey")],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(join)
        err = exc_info.value
        assert err.code == error_codes.JOIN_OUTPUT_COLUMN_CONFLICT
        assert err.offending_field == "partnerName"


# ---------------------------------------------------------------------------
# Spec examples end-to-end
# ---------------------------------------------------------------------------


class TestSpecExampleTwoStageAggregation:
    """需求.md §典型示例 1 — two-stage aggregation derives cleanly."""

    def test_two_stage_derivation(self):
        overdue_by_customer = from_(
            model="ReceivableLineQM",
            columns=[
                "salespersonId",
                "salespersonName",
                "customer$id AS customerId",
                "SUM(residualAmount) AS customerOverdue",
            ],
            group_by=["salespersonId", "salespersonName", "customerId"],
        )
        # First stage outputs are: salespersonId, salespersonName,
        # customerId, customerOverdue
        s1 = derive_schema(overdue_by_customer)
        assert s1.names() == [
            "salespersonId", "salespersonName", "customerId", "customerOverdue",
        ]

        second_stage = overdue_by_customer.query(
            columns=[
                "salespersonId",
                "salespersonName",
                "SUM(customerOverdue) AS arOverdue",
                "COUNT(*) AS arOverdueCustomerCount",
            ],
            group_by=["salespersonId", "salespersonName"],
            order_by=["-arOverdue"],
        )
        s2 = derive_schema(second_stage)
        assert s2.names() == [
            "salespersonId", "salespersonName", "arOverdue",
            "arOverdueCustomerCount",
        ]


class TestSpecExampleJoinThenFilter:
    """需求.md §典型示例 3 — join with explicit alias disambiguation."""

    def test_join_with_alias_disambiguation_works(self):
        sales = from_(
            model="SaleOrderQM",
            columns=[
                "partner$id AS partnerId",
                "partner$caption AS salesPartnerName",
                "SUM(amountTotal) AS totalSales",
            ],
            group_by=["partnerId", "salesPartnerName"],
        )
        leads = from_(
            model="CrmLeadQM",
            columns=[
                "partner$id AS leadPartnerId",
                "partner$caption AS leadPartnerName",
                "COUNT(*) AS leadCount",
            ],
            group_by=["leadPartnerId", "leadPartnerName"],
        )
        joined = sales.join(
            leads,
            type="left",
            on=[{"left": "partnerId", "op": "=", "right": "leadPartnerId"}],
        )
        schema = derive_schema(joined)
        # No conflict because the user aliased `partnerName` differently
        # on each side. Output preserves both sides in order.
        assert schema.names() == [
            "partnerId", "salesPartnerName", "totalSales",
            "leadPartnerId", "leadPartnerName", "leadCount",
        ]
