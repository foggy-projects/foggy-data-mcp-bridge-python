"""Tests for DbMeasureDef.filter_condition deprecation (v1.4 M4 Step 4.3).

Covers REQ-FORMULA-EXTEND §4.2.1: the field is retained for backwards-
compatible QM deserialisation, but constructing a ``DbMeasureDef`` that
actually sets ``filter_condition`` should emit a ``FutureWarning``
pointing authors at the ``formulaDef`` migration.
"""

from __future__ import annotations

import warnings

import pytest

from foggy.dataset_model.definitions.base import AggregationType
from foggy.dataset_model.definitions.measure import (
    DbMeasureDef,
    clear_filter_condition_warning_cache,
)


@pytest.fixture(autouse=True)
def _reset_warning_cache():
    """Ensure each test starts with a clean once-per-measure warning cache."""
    clear_filter_condition_warning_cache()
    yield
    clear_filter_condition_warning_cache()


class TestFilterConditionDeprecation:
    def test_nonempty_filter_condition_triggers_future_warning(self):
        with pytest.warns(FutureWarning, match=r"deprecated"):
            DbMeasureDef(
                name="posted_amount",
                column="amount",
                aggregation=AggregationType.SUM,
                filter_condition="state = 'posted'",
            )

    def test_warning_message_contains_measure_name(self):
        with pytest.warns(FutureWarning) as w:
            DbMeasureDef(
                name="net_posted",
                column="net",
                aggregation=AggregationType.SUM,
                filter_condition="state = 'posted'",
            )
        # At least one of the captured warnings must mention the measure
        # name and the §4.2.1 migration anchor.
        messages = [str(item.message) for item in w.list]
        assert any("net_posted" in m for m in messages)
        assert any("REQ-FORMULA-EXTEND §4.2.1" in m for m in messages)

    def test_warning_suggests_formula_migration(self):
        with pytest.warns(FutureWarning) as w:
            DbMeasureDef(
                name="m",
                column="c",
                aggregation=AggregationType.SUM,
                filter_condition="x > 0",
            )
        messages = [str(item.message) for item in w.list]
        # Migration hint lists both of the §4.2.1 recommended rewrites.
        assert any("sum(if(cond, col, 0))" in m for m in messages)
        assert any("count(distinct(if(cond, col, null)))" in m for m in messages)

    def test_empty_string_filter_condition_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            # Should not raise — empty string is falsy.
            DbMeasureDef(
                name="m",
                column="c",
                aggregation=AggregationType.SUM,
                filter_condition="",
            )

    def test_none_filter_condition_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            DbMeasureDef(
                name="m",
                column="c",
                aggregation=AggregationType.SUM,
                filter_condition=None,
            )

    def test_absent_filter_condition_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            DbMeasureDef(
                name="m",
                column="c",
                aggregation=AggregationType.SUM,
            )

    def test_warning_emitted_only_once_per_measure_name(self):
        """Reconstructing the same measure name should not re-warn.

        Prevents warning-storms when the same QM is re-validated repeatedly
        by downstream deserialisers.
        """
        # First construction emits a warning.
        with pytest.warns(FutureWarning):
            DbMeasureDef(
                name="storm_safe",
                column="c",
                aggregation=AggregationType.SUM,
                filter_condition="x > 0",
            )
        # Second construction with same name: no new warning.
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            DbMeasureDef(
                name="storm_safe",
                column="c",
                aggregation=AggregationType.SUM,
                filter_condition="x > 0",
            )

    def test_different_measure_names_each_warn_once(self):
        with pytest.warns(FutureWarning) as w:
            DbMeasureDef(name="a", column="c", aggregation=AggregationType.SUM,
                         filter_condition="x > 0")
            DbMeasureDef(name="b", column="c", aggregation=AggregationType.SUM,
                         filter_condition="x > 0")
        messages = [str(item.message) for item in w.list]
        assert any("'a'" in m for m in messages)
        assert any("'b'" in m for m in messages)

    def test_field_still_round_trips_via_dump(self):
        """Deprecation keeps the field serialisable so legacy QMs still load."""
        with pytest.warns(FutureWarning):
            m = DbMeasureDef(
                name="preserved",
                column="c",
                aggregation=AggregationType.SUM,
                filter_condition="y < 100",
            )
        assert m.filter_condition == "y < 100"
        assert m.model_dump(exclude_none=True)["filter_condition"] == "y < 100"
