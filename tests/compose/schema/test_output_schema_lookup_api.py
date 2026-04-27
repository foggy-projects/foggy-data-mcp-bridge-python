"""G10 PR2 · ``OutputSchema`` lookup API contract (Python mirror of
Java ``OutputSchemaLookupApiTest``).

Splits the new lookup surface into two regimes:

* Non-ambiguous (every column has ``is_ambiguous=False``) — works under
  both flag values; behaves identically to the M4 baseline.
* Ambiguous (≥2 columns share a name with ``is_ambiguous=True``) —
  only allowed when ``feature_flags.g10_enabled()`` is on; tests pin
  the flag explicitly to avoid env leakage.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose import feature_flags
from foggy.dataset_model.engine.compose.plan.plan import BaseModelPlan
from foggy.dataset_model.engine.compose.plan.plan_id import PlanId
from foggy.dataset_model.engine.compose.schema import error_codes
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError
from foggy.dataset_model.engine.compose.schema.output_schema import (
    ColumnSpec,
    OutputSchema,
)


def _stub_plan(model: str) -> BaseModelPlan:
    return BaseModelPlan(model=model, columns=("id",))


@pytest.fixture(autouse=True)
def _clear_override():
    yield
    feature_flags.override_g10_enabled(None)


# ---------------------------------------------------------------------------
# Non-ambiguous regime (legacy + G10 path identical)
# ---------------------------------------------------------------------------


class TestNonAmbiguous:
    def test_get_returns_single_or_none(self):
        s = OutputSchema.of([
            ColumnSpec(name="a", expression="a"),
            ColumnSpec(name="b", expression="SUM(b)"),
        ])
        assert s.get("a").name == "a"
        assert s.get("b").expression == "SUM(b)"
        assert s.get("missing") is None

    def test_get_all_returns_singleton_or_empty(self):
        s = OutputSchema.of([
            ColumnSpec(name="a", expression="a"),
            ColumnSpec(name="b", expression="b"),
        ])
        assert len(s.get_all("a")) == 1
        assert s.get_all("a")[0].name == "a"
        assert s.get_all("missing") == []

    def test_is_ambiguous_false_for_unique_or_missing(self):
        s = OutputSchema.of([ColumnSpec(name="a", expression="a")])
        assert s.is_ambiguous("a") is False
        assert s.is_ambiguous("missing") is False

    def test_require_unique_hit_or_missing(self):
        s = OutputSchema.of([ColumnSpec(name="a", expression="a")])
        assert s.require_unique("a").name == "a"
        with pytest.raises(KeyError):
            s.require_unique("missing")

    def test_index_of_unique_or_missing(self):
        s = OutputSchema.of([
            ColumnSpec(name="a", expression="a"),
            ColumnSpec(name="b", expression="b"),
        ])
        assert s.index_of("a") == 0
        assert s.index_of("b") == 1
        with pytest.raises(KeyError):
            s.index_of("missing")

    def test_flag_on_non_ambiguous_identical(self):
        feature_flags.override_g10_enabled(True)
        s = OutputSchema.of([
            ColumnSpec(name="a", expression="a"),
            ColumnSpec(name="b", expression="SUM(b)"),
        ])
        assert s.get("a").name == "a"
        assert s.get("missing") is None
        assert s.is_ambiguous("a") is False
        assert len(s.get_all("b")) == 1


# ---------------------------------------------------------------------------
# Legacy duplicate rejection (flag=False)
# ---------------------------------------------------------------------------


class TestLegacyDuplicateRejection:
    def test_plain_duplicate_rejected(self):
        with pytest.raises(ValueError):
            OutputSchema.of([
                ColumnSpec(name="name", expression="a"),
                ColumnSpec(name="name", expression="b"),
            ])

    def test_ambiguous_marked_rejected_under_legacy(self):
        feature_flags.override_g10_enabled(False)
        a = ColumnSpec(name="name", expression="name", is_ambiguous=True)
        b = ColumnSpec(name="name", expression="name", is_ambiguous=True)
        with pytest.raises(ValueError):
            OutputSchema.of([a, b])


# ---------------------------------------------------------------------------
# G10 ambiguous regime (flag=True)
# ---------------------------------------------------------------------------


class TestG10AmbiguousRegime:
    def _build(self) -> OutputSchema:
        feature_flags.override_g10_enabled(True)
        left_pid = PlanId.of(_stub_plan("OrderQM"))
        right_pid = PlanId.of(_stub_plan("CustomerQM"))
        order_id = ColumnSpec(
            name="orderId", expression="orderId",
            source_model="OrderQM", plan_provenance=left_pid,
        )
        left_name = ColumnSpec(
            name="name", expression="name",
            source_model="OrderQM", plan_provenance=left_pid,
            is_ambiguous=True,
        )
        right_name = ColumnSpec(
            name="name", expression="name",
            source_model="CustomerQM", plan_provenance=right_pid,
            is_ambiguous=True,
        )
        return OutputSchema.of([order_id, left_name, right_name])

    def test_duplicate_ambiguous_allowed(self):
        s = self._build()
        assert len(s) == 3
        assert s.names() == ["orderId", "name", "name"]
        assert s.is_ambiguous("name") is True
        assert s.is_ambiguous("orderId") is False
        assert s.contains("name") is True

    def test_get_all_returns_all_in_order(self):
        s = self._build()
        all_ = s.get_all("name")
        assert len(all_) == 2
        assert all_[0].source_model == "OrderQM"
        assert all_[1].source_model == "CustomerQM"

    def test_get_on_ambiguous_fails_fast(self):
        s = self._build()
        with pytest.raises(ComposeSchemaError) as ei:
            s.get("name")
        assert ei.value.code == error_codes.OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP
        assert ei.value.offending_field == "name"
        assert "ambiguous" in str(ei.value)
        assert "plan_provenance" in str(ei.value)

    def test_require_unique_on_ambiguous_fails_fast(self):
        s = self._build()
        with pytest.raises(ComposeSchemaError) as ei:
            s.require_unique("name")
        assert ei.value.code == error_codes.OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP

    def test_index_of_on_ambiguous_fails_fast(self):
        s = self._build()
        with pytest.raises(ComposeSchemaError) as ei:
            s.index_of("name")
        assert ei.value.code == error_codes.OUTPUT_SCHEMA_AMBIGUOUS_LOOKUP

    def test_non_ambiguous_columns_still_unique_lookup(self):
        s = self._build()
        assert s.get("orderId").name == "orderId"
        assert s.index_of("orderId") == 0
        assert s.is_ambiguous("orderId") is False
        assert len(s.get_all("orderId")) == 1

    def test_mixed_flags_rejected(self):
        feature_flags.override_g10_enabled(True)
        marked = ColumnSpec(
            name="name", expression="name",
            plan_provenance=PlanId.of(_stub_plan("L")),
            is_ambiguous=True,
        )
        plain = ColumnSpec(
            name="name", expression="name",
            plan_provenance=PlanId.of(_stub_plan("R")),
            is_ambiguous=False,
        )
        with pytest.raises(ValueError):
            OutputSchema.of([marked, plain])

    def test_identical_plan_provenance_rejected(self):
        feature_flags.override_g10_enabled(True)
        pid = PlanId.of(_stub_plan("Same"))
        a = ColumnSpec(name="name", expression="name",
                       plan_provenance=pid, is_ambiguous=True)
        b = ColumnSpec(name="name", expression="name",
                       plan_provenance=pid, is_ambiguous=True)
        with pytest.raises(ValueError) as ei:
            OutputSchema.of([a, b])
        assert "pure duplicate" in str(ei.value)
