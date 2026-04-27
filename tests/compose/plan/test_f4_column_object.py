"""G5 Phase 1 (F4) — Column object syntax tests (Python side).

Mirrors the Java :class:`F4ColumnObjectIntegrationTest`. Verifies the
``column_normalizer`` produces canonical string forms equivalent to F1-F3
strings, and that error codes (`COLUMN_*` prefix) are raised on invalid
F4 / F5 inputs.

Coverage
--------

* F4 alias only — ``{field, as}``
* F4 explicit aggregation — ``{field, agg, as}``
* F4 mixed array — F1 string + F3 string + F4 object
* F4 count_distinct — verifies normalized output that the SQL engine lowers
  to ``COUNT(DISTINCT field)``
* F4 error cases — ``COLUMN_FIELD_REQUIRED`` / ``COLUMN_AGG_NOT_SUPPORTED`` /
  ``COLUMN_AS_TYPE_INVALID`` / ``COLUMN_FIELD_INVALID_KEY``
* F5 placeholder — ``COLUMN_PLAN_NOT_VISIBLE`` (Phase 2 fail-loud)
* Integration with ``from_()`` — F4 entries in ``from_(columns=[...])`` produce
  a ``BaseModelPlan`` with the equivalent string columns
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import BaseModelPlan, from_
from foggy.dataset_model.engine.compose.plan.column_normalizer import (
    ALLOWED_AGG,
    normalize,
    normalize_columns,
    normalize_columns_to_strings,
)


# ---------------------------------------------------------------------------
# Unit tests — single-item normalize()
# ---------------------------------------------------------------------------


class TestNormalizeStringPassthrough:
    def test_plain_field_passthrough(self):
        assert normalize("salesAmount", 0) == "salesAmount"

    def test_field_alias_string_passthrough(self):
        assert normalize("name AS customer_name", 0) == "name AS customer_name"

    def test_aggregate_string_passthrough(self):
        assert normalize("SUM(amount) AS total", 0) == "SUM(amount) AS total"

    def test_function_string_passthrough(self):
        assert normalize("YEAR(orderDate) AS year", 0) == "YEAR(orderDate) AS year"

    def test_dimension_caption_passthrough(self):
        assert normalize("product$caption", 0) == "product$caption"

    def test_nested_dimension_passthrough(self):
        assert normalize("product.category$caption", 0) == "product.category$caption"

    def test_none_passthrough(self):
        assert normalize(None, 0) is None


class TestNormalizeF4Object:
    def test_field_only_to_string(self):
        # {field} → "field"
        assert normalize({"field": "salesAmount"}, 0) == "salesAmount"

    def test_field_and_alias(self):
        # {field, as} → "field AS alias"
        assert (
            normalize({"field": "name", "as": "customer_name"}, 0)
            == "name AS customer_name"
        )

    def test_field_and_agg(self):
        # {field, agg} → "AGG(field)"
        assert normalize({"field": "amount", "agg": "sum"}, 0) == "SUM(amount)"

    def test_field_agg_and_alias(self):
        # {field, agg, as} → "AGG(field) AS alias"
        assert (
            normalize({"field": "amount", "agg": "sum", "as": "total"}, 0)
            == "SUM(amount) AS total"
        )

    def test_agg_case_insensitive(self):
        # agg whitelist is case-insensitive; output uppercase
        assert (
            normalize({"field": "amount", "agg": "SUM", "as": "total"}, 0)
            == "SUM(amount) AS total"
        )
        assert (
            normalize({"field": "amount", "agg": "Avg", "as": "av"}, 0)
            == "AVG(amount) AS av"
        )

    def test_count_distinct_lowering(self):
        # count_distinct → COUNT_DISTINCT(field) which the engine lowers
        # to COUNT(DISTINCT field)
        assert (
            normalize({"field": "customer_id", "agg": "count_distinct", "as": "u"}, 0)
            == "COUNT_DISTINCT(customer_id) AS u"
        )

    def test_field_strip_whitespace(self):
        # field is trimmed
        assert normalize({"field": "  name  ", "as": "n"}, 0) == "name AS n"

    def test_alias_strip_whitespace(self):
        # alias is trimmed; empty after trim treated as no alias
        assert normalize({"field": "name", "as": "  alias  "}, 0) == "name AS alias"
        assert normalize({"field": "name", "as": "   "}, 0) == "name"

    def test_alias_none_treated_as_no_alias(self):
        assert normalize({"field": "name", "as": None}, 0) == "name"

    def test_all_six_aggregates_covered(self):
        # Sanity: whitelist matches spec §2.3 (sum/avg/count/max/min/count_distinct)
        for agg in sorted(ALLOWED_AGG):
            result = normalize({"field": "x", "agg": agg, "as": "r"}, 0)
            assert result == f"{agg.upper()}(x) AS r"


class TestF4ErrorCodes:
    def test_missing_field_raises_field_required(self):
        with pytest.raises(ValueError, match="COLUMN_FIELD_REQUIRED"):
            normalize({"agg": "sum", "as": "x"}, 3)

    def test_blank_field_raises_field_required(self):
        with pytest.raises(ValueError, match="COLUMN_FIELD_REQUIRED"):
            normalize({"field": "  ", "agg": "sum"}, 0)

    def test_non_string_field_raises_field_required(self):
        with pytest.raises(ValueError, match="COLUMN_FIELD_REQUIRED"):
            normalize({"field": 123}, 0)

    def test_unknown_agg_raises_agg_not_supported(self):
        with pytest.raises(ValueError, match="COLUMN_AGG_NOT_SUPPORTED"):
            normalize({"field": "x", "agg": "median"}, 0)

    def test_blank_agg_raises_agg_not_supported(self):
        with pytest.raises(ValueError, match="COLUMN_AGG_NOT_SUPPORTED"):
            normalize({"field": "x", "agg": "  "}, 0)

    def test_non_string_alias_raises_as_type_invalid(self):
        with pytest.raises(ValueError, match="COLUMN_AS_TYPE_INVALID"):
            normalize({"field": "x", "as": 123}, 0)

    def test_unknown_key_raises_invalid_key(self):
        with pytest.raises(ValueError, match="COLUMN_FIELD_INVALID_KEY"):
            normalize({"field": "x", "extras": "nope"}, 0)


class TestF5PlaceholderFailLoud:
    def test_plan_key_raises_plan_not_visible(self):
        # F5 plan-qualified form is Phase 2; Phase 1 fails loudly with a
        # clear error explaining the workaround.
        with pytest.raises(ValueError, match="COLUMN_PLAN_NOT_VISIBLE"):
            normalize({"plan": object(), "field": "name", "as": "x"}, 0)

    def test_plan_key_alone_also_rejected(self):
        with pytest.raises(ValueError, match="COLUMN_PLAN_NOT_VISIBLE"):
            normalize({"plan": object(), "field": "name"}, 0)


# ---------------------------------------------------------------------------
# List-level normalize_columns / normalize_columns_to_strings
# ---------------------------------------------------------------------------


class TestNormalizeColumnsList:
    def test_pure_strings_passthrough(self):
        assert normalize_columns(["a", "b AS x"]) == ["a", "b AS x"]

    def test_pure_objects_normalized(self):
        cols = [
            {"field": "salesAmount", "agg": "sum", "as": "total"},
            {"field": "name", "as": "customer_name"},
        ]
        assert normalize_columns(cols) == [
            "SUM(salesAmount) AS total",
            "name AS customer_name",
        ]

    def test_mixed_array(self):
        cols = [
            "product$id",
            "SUM(amount) AS totalAmt",
            {"field": "salesAmount", "agg": "avg", "as": "avgAmt"},
        ]
        assert normalize_columns(cols) == [
            "product$id",
            "SUM(amount) AS totalAmt",
            "AVG(salesAmount) AS avgAmt",
        ]

    def test_empty_list(self):
        assert normalize_columns([]) == []

    def test_none_input(self):
        assert normalize_columns(None) == []

    def test_to_strings_skips_none(self):
        # None entries skipped in to_strings variant (matches Java legacy behaviour)
        assert normalize_columns_to_strings(["a", None, "b"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# Integration with from_() — verifies wired entry point
# ---------------------------------------------------------------------------


class TestFromIntegration:
    def test_from_accepts_f4_object(self):
        # from_() with F4 object in columns list should produce a BaseModelPlan
        # whose .columns tuple contains the canonical string form.
        plan = from_(
            model="FactSalesQueryModel",
            columns=[
                "product$id",
                {"field": "salesAmount", "agg": "sum", "as": "total"},
            ],
            group_by=["product$id"],
        )
        assert isinstance(plan, BaseModelPlan)
        assert plan.columns == ("product$id", "SUM(salesAmount) AS total")

    def test_from_accepts_count_distinct_f4(self):
        plan = from_(
            model="FactSalesQueryModel",
            columns=[{"field": "customer_id", "agg": "count_distinct", "as": "uniq"}],
        )
        assert plan.columns == ("COUNT_DISTINCT(customer_id) AS uniq",)

    def test_from_rejects_invalid_f4(self):
        with pytest.raises(ValueError, match="COLUMN_FIELD_REQUIRED"):
            from_(
                model="FactSalesQueryModel",
                columns=[{"agg": "sum", "as": "x"}],  # missing field
            )

    def test_from_rejects_unknown_agg(self):
        with pytest.raises(ValueError, match="COLUMN_AGG_NOT_SUPPORTED"):
            from_(
                model="FactSalesQueryModel",
                columns=[{"field": "x", "agg": "median"}],
            )

    def test_from_rejects_f5_phase_2_fail_loud(self):
        with pytest.raises(ValueError, match="COLUMN_PLAN_NOT_VISIBLE"):
            from_(
                model="FactSalesQueryModel",
                columns=[{"plan": object(), "field": "name"}],
            )

    def test_existing_string_only_columns_unchanged(self):
        # Backward compat: pure string columns continue working
        plan = from_(
            model="FactSalesQueryModel",
            columns=["product$id", "SUM(amount) AS total"],
        )
        assert plan.columns == ("product$id", "SUM(amount) AS total")
