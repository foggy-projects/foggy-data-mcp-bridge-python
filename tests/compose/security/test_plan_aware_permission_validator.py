"""G10 PR4 · ``ComposePlanAwarePermissionValidator`` contract (Python
mirror of Java ``ComposePlanAwarePermissionValidatorTest``)."""

from __future__ import annotations

from typing import List

import pytest

from foggy.dataset_model.engine.compose.plan.plan import (
    BaseModelPlan,
    DerivedQueryPlan,
    PlanColumnRef,
)
from foggy.dataset_model.engine.compose.plan.plan_id import PlanId
from foggy.dataset_model.engine.compose.schema import error_codes
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError
from foggy.dataset_model.engine.compose.schema.output_schema import (
    ColumnSpec,
    OutputSchema,
)
from foggy.dataset_model.engine.compose.security import (
    plan_aware_permission_validator,
)
from foggy.dataset_model.engine.compose.security.models import ModelBinding
from foggy.dataset_model.engine.compose.security.plan_field_access_context import (
    PlanFieldAccessContext,
)


def _base(model: str, columns: List[str]) -> BaseModelPlan:
    return BaseModelPlan(model=model, columns=tuple(columns))


def _spec_with_provenance(
    name: str, plan: BaseModelPlan = None, ambiguous: bool = False
) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        expression=name,
        plan_provenance=PlanId.of(plan) if plan is not None else None,
        is_ambiguous=ambiguous,
    )


# ---------------------------------------------------------------------------
# F5 plan-qualified routing
# ---------------------------------------------------------------------------
#
# Architectural note: Python's ``DerivedQueryPlan.columns`` is
# ``Tuple[str, ...]`` and rejects ``PlanColumnRef`` at construction.
# Plan-qualified routing is dead code in Python until G5 Phase 2
# enables F5 syntax through ``column_normalizer``. We exercise the
# private ``_validate_plan_qualified`` helper directly to verify
# parity with Java; the public ``validate(...)`` reaches it only when
# F5 lands.


class TestPlanQualified:
    def test_allowed_in_whitelist_passes(self):
        order = _base("OrderQM", ["orderId", "customerId"])
        ref = PlanColumnRef(plan=order, name="orderId")
        ctx = PlanFieldAccessContext().bind(
            order, ModelBinding(field_access=["orderId", "customerId"])
        )
        # No raise.
        plan_aware_permission_validator._validate_plan_qualified(ref, ctx)

    def test_unknown_plan_fails_closed(self):
        stranger = _base("StrangerQM", ["x"])
        ref = PlanColumnRef(plan=stranger, name="x")
        ctx = PlanFieldAccessContext().bind(
            _base("OrderQM", ["orderId"]), ModelBinding()
        )

        with pytest.raises(ComposeSchemaError) as ei:
            plan_aware_permission_validator._validate_plan_qualified(ref, ctx)
        assert ei.value.code == error_codes.COLUMN_PLAN_NOT_BOUND
        assert ei.value.phase == error_codes.PHASE_PERMISSION_VALIDATE
        assert ei.value.offending_field == "x"

    def test_denied_by_whitelist(self):
        order = _base("OrderQM", ["orderId", "secret"])
        ref = PlanColumnRef(plan=order, name="secret")
        ctx = PlanFieldAccessContext().bind(
            order, ModelBinding(field_access=["orderId"])
        )

        with pytest.raises(ComposeSchemaError) as ei:
            plan_aware_permission_validator._validate_plan_qualified(ref, ctx)
        assert ei.value.code == error_codes.FIELD_ACCESS_DENIED
        assert ei.value.phase == error_codes.PHASE_PERMISSION_VALIDATE
        assert ei.value.offending_field == "secret"

    def test_no_whitelist_means_unrestricted(self):
        order = _base("OrderQM", ["orderId"])
        ref = PlanColumnRef(plan=order, name="orderId")
        ctx = PlanFieldAccessContext().bind(order, ModelBinding())

        # No raise — no whitelist = no restriction.
        plan_aware_permission_validator._validate_plan_qualified(ref, ctx)

    def test_dimension_suffix_stripped(self):
        order = _base("OrderQM", ["salesDate"])
        ref = PlanColumnRef(plan=order, name="salesDate$id")
        ctx = PlanFieldAccessContext().bind(
            order, ModelBinding(field_access=["salesDate"])
        )
        # No raise — strip $id matches base name in whitelist.
        plan_aware_permission_validator._validate_plan_qualified(ref, ctx)


# ---------------------------------------------------------------------------
# Bare-field resolution (§6.4)
# ---------------------------------------------------------------------------


class TestBareField:
    def test_unknown_field_rejected(self):
        order = _base("OrderQM", ["orderId"])
        derived = DerivedQueryPlan(source=order, columns=("totallyMissing",))

        schema = OutputSchema.of([_spec_with_provenance("orderId", order)])
        ctx = PlanFieldAccessContext().bind(order, ModelBinding())

        with pytest.raises(ComposeSchemaError) as ei:
            plan_aware_permission_validator.validate(derived, schema, ctx)
        assert ei.value.code == error_codes.COLUMN_FIELD_NOT_FOUND
        assert ei.value.offending_field == "totallyMissing"

    def test_ambiguous_field_rejected(self):
        # The conftest autouse ``_clear_g10_override`` fixture restores
        # the default flag on teardown, so no try/finally needed here.
        from foggy.dataset_model.engine.compose import feature_flags
        feature_flags.override_g10_enabled(True)

        customers = _base("CustomerQM", ["name"])
        orders = _base("OrderQM", ["name"])
        wrapper = DerivedQueryPlan(source=customers, columns=("name",))

        # mimics PR2 derive_join output: both occurrences ambiguous,
        # distinct provenance.
        schema = OutputSchema.of([
            _spec_with_provenance("name", customers, ambiguous=True),
            _spec_with_provenance("name", orders, ambiguous=True),
        ])
        ctx = (
            PlanFieldAccessContext()
            .bind(customers, ModelBinding(field_access=["name"]))
            .bind(orders, ModelBinding(field_access=["name"]))
        )

        with pytest.raises(ComposeSchemaError) as ei:
            plan_aware_permission_validator.validate(wrapper, schema, ctx)
        assert ei.value.code == error_codes.JOIN_AMBIGUOUS_COLUMN
        assert "plan-qualified" in str(ei.value)

    def test_unique_resolved_routes_via_provenance_allow(self):
        order = _base("OrderQM", ["orderId"])
        derived = DerivedQueryPlan(source=order, columns=("orderId",))

        schema = OutputSchema.of([_spec_with_provenance("orderId", order)])
        allow = PlanFieldAccessContext().bind(
            order, ModelBinding(field_access=["orderId"])
        )
        plan_aware_permission_validator.validate(derived, schema, allow)  # no raise

    def test_unique_resolved_routes_via_provenance_deny(self):
        order = _base("OrderQM", ["orderId"])
        derived = DerivedQueryPlan(source=order, columns=("orderId",))

        schema = OutputSchema.of([_spec_with_provenance("orderId", order)])
        deny = PlanFieldAccessContext().bind(
            order, ModelBinding(field_access=["other"])
        )
        with pytest.raises(ComposeSchemaError) as ei:
            plan_aware_permission_validator.validate(derived, schema, deny)
        assert ei.value.code == error_codes.FIELD_ACCESS_DENIED

    def test_unique_without_provenance_defers_to_legacy(self):
        order = _base("OrderQM", ["orderId"])
        derived = DerivedQueryPlan(source=order, columns=("orderId",))

        # No provenance on the spec — legacy single-base case.
        schema = OutputSchema.of([ColumnSpec(name="orderId", expression="orderId")])
        ctx = PlanFieldAccessContext.empty()
        plan_aware_permission_validator.validate(derived, schema, ctx)  # no raise

    def test_alias_form_resolved_by_alias(self):
        order = _base("OrderQM", ["orderId", "amount"])
        derived = DerivedQueryPlan(
            source=order, columns=("SUM(amount) AS total",)
        )

        schema = OutputSchema.of([_spec_with_provenance("total", order)])
        ctx = PlanFieldAccessContext().bind(
            order, ModelBinding(field_access=["total"])
        )
        plan_aware_permission_validator.validate(derived, schema, ctx)  # no raise


# ---------------------------------------------------------------------------
# Argument-validation guards
# ---------------------------------------------------------------------------


class TestArgumentGuards:
    def test_none_plan_rejected(self):
        with pytest.raises(TypeError):
            plan_aware_permission_validator.validate(
                None, OutputSchema.of([]), PlanFieldAccessContext.empty()
            )

    def test_none_schema_rejected(self):
        p = _base("X", ["a"])
        with pytest.raises(TypeError):
            plan_aware_permission_validator.validate(
                p, None, PlanFieldAccessContext.empty()
            )

    def test_none_context_rejected(self):
        p = _base("X", ["a"])
        with pytest.raises(TypeError):
            plan_aware_permission_validator.validate(p, OutputSchema.of([]), None)
