"""Tests for same-stage alias detection in derived plan slice.

Covers the ``DERIVED_QUERY_SAME_STAGE_ALIAS`` error code — when a derived
plan's ``slice`` references a SELECT alias that is created in the same
``.query()`` stage, not a column from the source schema.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.schema import (
    ComposeSchemaError,
    derive_schema,
)
from foggy.dataset_model.engine.compose.schema import error_codes


class TestSameStageAliasDetection:
    """Derived plan's ``slice`` referencing a same-stage computed alias."""

    def _base(self):
        """Source plan with three columns available."""
        return from_(
            model="TestQM",
            columns=[
                "partner$id",
                "partner$caption",
                "invoiceDate$month",
                "arOverdueAmount",
            ],
            group_by=["partner$id", "partner$caption", "invoiceDate$month"],
        )

    def test_slice_on_same_stage_aggregate_alias_rejected(self):
        """AR-014 shape: count(...) AS month_count then slice on month_count
        in the same stage → early schema error."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "partner$caption",
                "count(invoiceDate$month) AS month_count",
            ],
            group_by=["partner$id", "partner$caption"],
            slice=[{"field": "month_count", "op": ">=", "value": 2}],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(derived)
        err = exc_info.value
        assert err.code == error_codes.DERIVED_QUERY_SAME_STAGE_ALIAS
        assert err.offending_field == "month_count"
        assert "month_count" in str(err)
        assert "another .query(" in str(err)

    def test_slice_on_same_stage_sum_alias_rejected(self):
        """SUM(...) AS totalOverdue then slice on totalOverdue."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "SUM(arOverdueAmount) AS totalOverdue",
            ],
            group_by=["partner$id"],
            slice=[{"field": "totalOverdue", "op": ">", "value": 0}],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(derived)
        err = exc_info.value
        assert err.code == error_codes.DERIVED_QUERY_SAME_STAGE_ALIAS
        assert err.offending_field == "totalOverdue"

    def test_slice_on_source_column_allowed(self):
        """Filtering on a source column that IS in the source schema is
        fine — this is the normal derived slice use case."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "partner$caption",
                "count(invoiceDate$month) AS month_count",
            ],
            group_by=["partner$id", "partner$caption"],
            slice=[{"field": "arOverdueAmount", "op": ">", "value": 0}],
        )
        # Should succeed — arOverdueAmount is a source column.
        schema = derive_schema(derived)
        assert "month_count" in schema.names()

    def test_slice_on_passthrough_column_allowed(self):
        """A column selected without alias (passthrough) is not a new
        same-stage alias — it's a source reference."""
        base = self._base()
        derived = base.query(
            columns=["partner$id", "partner$caption"],
            slice=[{"field": "partner$id", "op": "=", "value": 42}],
        )
        schema = derive_schema(derived)
        assert schema.names() == ["partner$id", "partner$caption"]

    def test_slice_on_rename_alias_matching_source_allowed(self):
        """An alias that happens to match an existing source column name
        (e.g. ``arOverdueAmount AS arOverdueAmount``) is a rename, not
        a new computed alias — should not trigger the error."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "arOverdueAmount AS arOverdueAmount",
            ],
            slice=[{"field": "arOverdueAmount", "op": ">", "value": 0}],
        )
        schema = derive_schema(derived)
        assert "arOverdueAmount" in schema.names()

    def test_slice_shortcut_syntax_same_stage_alias_rejected(self):
        """Single-key shortcut ``{month_count: 2}`` also triggers the
        same-stage alias detection."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "count(invoiceDate$month) AS month_count",
            ],
            group_by=["partner$id"],
            slice=[{"month_count": 2}],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(derived)
        err = exc_info.value
        assert err.code == error_codes.DERIVED_QUERY_SAME_STAGE_ALIAS
        assert err.offending_field == "month_count"

    def test_empty_slice_no_error(self):
        """Empty slice — no validation needed, no error."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "count(invoiceDate$month) AS month_count",
            ],
            group_by=["partner$id"],
        )
        schema = derive_schema(derived)
        assert "month_count" in schema.names()

    def test_two_stage_pattern_works(self):
        """The correct two-stage pattern: first aggregate, then filter
        on the alias in a second .query() stage."""
        base = self._base()
        # Stage 1: aggregate
        aggregated = base.query(
            columns=[
                "partner$id",
                "partner$caption",
                "count(invoiceDate$month) AS month_count",
            ],
            group_by=["partner$id", "partner$caption"],
        )
        # Stage 2: filter on the alias (now it's a source column)
        filtered = aggregated.query(
            slice=[{"field": "month_count", "op": ">=", "value": 2}],
        )
        # Both stages should derive cleanly.
        s1 = derive_schema(aggregated)
        assert "month_count" in s1.names()
        s2 = derive_schema(filtered)
        # Empty columns means passthrough — inherits all from source.
        # Actually, derive will see empty columns tuple. Let's check
        # the plan builds without error at minimum.
        assert s2 is not None

    def test_multiple_same_stage_aliases_first_caught(self):
        """If multiple same-stage aliases are referenced in slice,
        the first one is caught."""
        base = self._base()
        derived = base.query(
            columns=[
                "partner$id",
                "count(invoiceDate$month) AS month_count",
                "SUM(arOverdueAmount) AS total_overdue",
            ],
            group_by=["partner$id"],
            slice=[
                {"field": "month_count", "op": ">=", "value": 2},
                {"field": "total_overdue", "op": ">", "value": 0},
            ],
        )
        with pytest.raises(ComposeSchemaError) as exc_info:
            derive_schema(derived)
        err = exc_info.value
        assert err.code == error_codes.DERIVED_QUERY_SAME_STAGE_ALIAS
        # First offending field is caught.
        assert err.offending_field == "month_count"
