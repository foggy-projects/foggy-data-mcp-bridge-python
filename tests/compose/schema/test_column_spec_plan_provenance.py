"""G10 PR1 · ``ColumnSpec`` new fields ``plan_provenance`` + ``is_ambiguous``
(Python mirror of Java ``ColumnSpecPlanProvenanceTest``).

Verifies that the new fields are exposed via dataclass kwargs + accessor,
and that PR1's **真零行为变化** guarantee holds — the new fields do *not*
participate in ``__eq__`` or ``__hash__``, so existing equality-based
tests continue to pass unchanged.
"""

from __future__ import annotations

from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan
from foggy.dataset_model.engine.compose.plan.plan_id import PlanId
from foggy.dataset_model.engine.compose.schema.output_schema import ColumnSpec


def stub_plan(model: str) -> BaseModelPlan:
    return BaseModelPlan(model=model, columns=("id",))


# ---------------------------------------------------------------------------
# 默认值（PR1 真零行为）
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_minimal_construction_defaults(self):
        c = ColumnSpec(name="orderId", expression="orderId")
        assert c.plan_provenance is None, "default plan_provenance must be None"
        assert c.is_ambiguous is False, "default is_ambiguous must be False"

    def test_with_other_fields_defaults_unset(self):
        c = ColumnSpec(name="x", expression="x", source_model="M",
                       has_explicit_alias=True)
        assert c.plan_provenance is None
        assert c.is_ambiguous is False


# ---------------------------------------------------------------------------
# Constructor accepts new fields
# ---------------------------------------------------------------------------


class TestConstructorAcceptsNewFields:
    def test_plan_provenance_roundtrip(self):
        pid = PlanId.of(stub_plan("CustomerQM"))
        c = ColumnSpec(name="name", expression="name", plan_provenance=pid)
        assert c.plan_provenance is pid, \
            "plan_provenance accessor must return the exact PlanId set"

    def test_is_ambiguous_roundtrip(self):
        c = ColumnSpec(name="name", expression="name", is_ambiguous=True)
        assert c.is_ambiguous is True

    def test_coexist_with_existing_fields(self):
        pid = PlanId.of(stub_plan("OrderQM"))
        c = ColumnSpec(
            name="orderName",
            expression="name AS orderName",
            source_model="OrderQM",
            has_explicit_alias=True,
            plan_provenance=pid,
            is_ambiguous=True,
        )
        assert c.name == "orderName"
        assert c.source_model == "OrderQM"
        assert c.has_explicit_alias is True
        assert c.plan_provenance is pid
        assert c.is_ambiguous is True


# ---------------------------------------------------------------------------
# PR1 真零行为：新字段不参与 equality / hash
# ---------------------------------------------------------------------------


class TestEqualityUnchanged:
    def test_different_provenance_still_equal(self):
        p1 = PlanId.of(stub_plan("M1"))
        p2 = PlanId.of(stub_plan("M2"))
        a = ColumnSpec(name="x", expression="x", plan_provenance=p1)
        b = ColumnSpec(name="x", expression="x", plan_provenance=p2)
        assert a == b, \
            "PR1 真零行为: plan_provenance not in equals — existing tests must not break"
        assert hash(a) == hash(b), \
            "PR1 真零行为: hash also unaffected by plan_provenance"

    def test_different_ambiguity_still_equal(self):
        a = ColumnSpec(name="x", expression="x", is_ambiguous=False)
        b = ColumnSpec(name="x", expression="x", is_ambiguous=True)
        assert a == b, "PR1 真零行为: is_ambiguous not in equals"
        assert hash(a) == hash(b)

    def test_existing_field_equality_preserved(self):
        a = ColumnSpec(name="x", expression="x", source_model="M1")
        b = ColumnSpec(name="x", expression="x", source_model="M2")
        assert a != b, \
            "Existing equality contract (source_model) must remain enforced"
