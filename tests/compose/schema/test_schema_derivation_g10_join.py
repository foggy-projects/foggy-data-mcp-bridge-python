"""G10 PR2 · ``derive_schema`` on ``JoinPlan`` flag-gated behaviour
(Python mirror of Java ``SchemaDerivationG10JoinTest``).

Mirrors the legacy join-overlap coverage but pins
``feature_flags.g10_enabled`` explicitly so each regime is verified
in isolation.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose import feature_flags
from foggy.dataset_model.engine.compose.plan.dsl import from_
from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    JoinOn,
    JoinPlan,
)
from foggy.dataset_model.engine.compose.schema import error_codes
from foggy.dataset_model.engine.compose.schema.derive import derive_schema
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError


def _base(model: str, columns) -> BaseModelPlan:
    return from_(model=model, columns=list(columns))


def _partner_join() -> JoinPlan:
    left = _base("OrderQM", ["orderId", "name", "amount"])
    right = _base("CustomerQM", ["customerId", "name", "rating"])
    return JoinPlan(
        left=left,
        right=right,
        type="left",
        on=(JoinOn(left="orderId", op="=", right="customerId"),),
    )


@pytest.fixture(autouse=True)
def _clear_override():
    yield
    feature_flags.override_g10_enabled(None)


# ---------------------------------------------------------------------------
# Legacy (flag=False) — JOIN_OUTPUT_COLUMN_CONFLICT 仍抛
# ---------------------------------------------------------------------------


class TestFlagOffLegacy:
    def test_overlap_still_throws(self):
        feature_flags.override_g10_enabled(False)
        with pytest.raises(ComposeSchemaError) as ei:
            derive_schema(_partner_join())
        assert ei.value.code == error_codes.JOIN_OUTPUT_COLUMN_CONFLICT
        assert ei.value.offending_field == "name"

    def test_non_overlap_strips_source_model(self):
        feature_flags.override_g10_enabled(False)
        left = _base("SalesQM", ["partnerId", "totalSales"])
        right = _base("LeadsQM", ["partnerKey", "leadCount"])
        join = JoinPlan(
            left=left, right=right, type="left",
            on=(JoinOn(left="partnerId", op="=", right="partnerKey"),),
        )
        schema = derive_schema(join)
        for c in schema.columns:
            assert c.source_model is None, \
                f"flag=False join must clear source_model, col={c.name}"
            assert c.plan_provenance is None
            assert c.is_ambiguous is False


# ---------------------------------------------------------------------------
# G10 (flag=True) — 同名列被标 is_ambiguous + 携带 plan_provenance
# ---------------------------------------------------------------------------


class TestFlagOnG10:
    def test_overlap_marked_ambiguous_not_thrown(self):
        feature_flags.override_g10_enabled(True)
        join = _partner_join()
        schema = derive_schema(join)
        # 6 columns: orderId, name, amount + customerId, name, rating
        assert len(schema) == 6
        assert schema.is_ambiguous("name"), \
            "重名列 'name' 必须被标为 ambiguous"
        assert not schema.is_ambiguous("orderId")
        assert not schema.is_ambiguous("customerId")

        both_names = schema.get_all("name")
        assert len(both_names) == 2
        for c in both_names:
            assert c.is_ambiguous, "每个歧义列必须自带 is_ambiguous=True"
            assert c.plan_provenance is not None

    def test_plan_provenance_distinguishes_sides(self):
        feature_flags.override_g10_enabled(True)
        join = _partner_join()
        schema = derive_schema(join)
        ambiguous = schema.get_all("name")
        left_pid = ambiguous[0].plan_provenance
        right_pid = ambiguous[1].plan_provenance
        assert left_pid is not None and right_pid is not None
        assert left_pid != right_pid
        assert left_pid.resolve() is join.left
        assert right_pid.resolve() is join.right

    def test_unique_columns_carry_provenance(self):
        feature_flags.override_g10_enabled(True)
        join = _partner_join()
        schema = derive_schema(join)
        order_id = schema.get("orderId")
        assert order_id.plan_provenance is not None
        assert order_id.source_model == "OrderQM"
        assert order_id.plan_provenance.resolve() is join.left
        assert order_id.is_ambiguous is False

        customer_id = schema.get("customerId")
        assert customer_id.plan_provenance.resolve() is join.right
        assert customer_id.source_model == "CustomerQM"

    def test_non_overlap_also_sets_provenance(self):
        feature_flags.override_g10_enabled(True)
        left = _base("SalesQM", ["partnerId", "totalSales"])
        right = _base("LeadsQM", ["partnerKey", "leadCount"])
        join = JoinPlan(
            left=left, right=right, type="left",
            on=(JoinOn(left="partnerId", op="=", right="partnerKey"),),
        )
        schema = derive_schema(join)
        assert len(schema) == 4
        for c in schema.columns:
            assert c.plan_provenance is not None, \
                f"G10 path: col {c.name} must have plan_provenance"
            assert not c.is_ambiguous
            assert c.source_model is not None, \
                f"G10 path preserves source_model: col {c.name}"

    def test_join_on_validations_still_work(self):
        feature_flags.override_g10_enabled(True)
        left = _base("A", ["x"])
        right = _base("B", ["y"])

        bad_left = JoinPlan(
            left=left, right=right, type="left",
            on=(JoinOn(left="missing", op="=", right="y"),),
        )
        with pytest.raises(ComposeSchemaError) as ei:
            derive_schema(bad_left)
        assert ei.value.code == error_codes.JOIN_ON_LEFT_UNKNOWN_FIELD

        bad_right = JoinPlan(
            left=left, right=right, type="left",
            on=(JoinOn(left="x", op="=", right="missing"),),
        )
        with pytest.raises(ComposeSchemaError) as ei:
            derive_schema(bad_right)
        assert ei.value.code == error_codes.JOIN_ON_RIGHT_UNKNOWN_FIELD

    def test_downstream_get_on_ambiguous_fails(self):
        feature_flags.override_g10_enabled(True)
        schema = derive_schema(_partner_join())
        with pytest.raises(ComposeSchemaError) as ei:
            schema.get("name")
        assert ei.value.code == error_codes.OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP
