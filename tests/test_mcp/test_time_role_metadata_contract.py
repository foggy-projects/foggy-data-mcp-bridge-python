"""Tests for timeRole / recommendedUse metadata contract fix.

BUG-1: describe_model_internal must expose timeRole / recommendedUse
       for fields that declare them.
BUG-2: timeWindow validation must accept property-level timeRole fields
       (e.g. move$date) while rejecting synthetic suffixes.
"""

import pytest
from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DimensionJoinDef,
    DimensionPropertyDef,
    DbModelMeasureImpl,
)
from foggy.dataset_model.definitions.base import DbColumnDef, ColumnType, AggregationType
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.dataset_model.semantic.time_window import (
    collect_time_window_field_sets,
    TimeWindowDef,
    TimeWindowValidator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_payment_model() -> DbTableModelImpl:
    """Build a minimal OdooAccountPaymentModel replica for testing.

    The 'move' dimension join has a 'date' property with:
        timeRole=business_date, data_type=DAY
    """
    date_prop = DimensionPropertyDef(
        column="date",
        name="date",
        caption="Accounting Date",
        data_type="DAY",
        timeRole="business_date",
        recommendedUse=(
            "Primary payment business date for payment trend and period pivot queries."
        ),
    )
    company_prop = DimensionPropertyDef(
        column="company_id",
        name="companyId",
        caption="Company ID",
        data_type="INTEGER",
    )
    move_join = DimensionJoinDef(
        name="move",
        table_name="account_move",
        foreign_key="move_id",
        primary_key="id",
        caption_column="name",
        caption="Journal Entry",
        description="Linked journal entry",
        properties=[company_prop, date_prop],
    )
    amount_measure = DbModelMeasureImpl(
        name="amount",
        alias="Amount",
        column="amount",
        aggregation=AggregationType.SUM,
    )
    model = DbTableModelImpl(
        name="OdooAccountPaymentModel",
        alias="Payments",
        source_table="account_payment",
        dimensions={},
        measures={"amount": amount_measure},
        columns={},
        dimension_joins=[move_join],
    )
    return model


def _make_invoice_model() -> DbTableModelImpl:
    """Build a minimal OdooAccountMoveModel with fact-table timeRole columns."""
    invoice_date_col = DbColumnDef(
        name="invoice_date",
        alias="Invoice Date",
        column_type=ColumnType.DATE,
        timeRole="business_date",
        recommendedUse=(
            "Primary invoice/bill business date for timeWindow, revenue, AP, "
            "and period pivot queries."
        ),
    )
    date_col = DbColumnDef(
        name="date",
        alias="Accounting Date",
        column_type=ColumnType.DATE,
        timeRole="posting_date",
        recommendedUse="Use for GL posting-period analysis.",
    )
    create_date_col = DbColumnDef(
        name="create_date",
        alias="Created On",
        column_type=ColumnType.DATETIME,
        # No timeRole — should NOT be added to time_fields
    )
    amount_total = DbModelMeasureImpl(
        name="amount_total",
        alias="Total",
        column="amount_total",
        aggregation=AggregationType.SUM,
    )
    model = DbTableModelImpl(
        name="OdooAccountMoveModel",
        alias="Invoices & Journal Entries",
        source_table="account_move",
        dimensions={},
        measures={"amount_total": amount_total},
        columns={
            "invoice_date": invoice_date_col,
            "date": date_col,
            "create_date": create_date_col,
        },
        dimension_joins=[],
    )
    return model


def _make_service_with(model: DbTableModelImpl) -> SemanticQueryService:
    svc = SemanticQueryService()
    svc.register_model(model)
    return svc


# ---------------------------------------------------------------------------
# BUG-1 Tests: describe_model_internal exposes timeRole / recommendedUse
# ---------------------------------------------------------------------------

class TestTimeRoleVisibleInMarkdown:
    """BUG-1: timeRole/recommendedUse must appear in the LLM-visible markdown."""

    def test_join_property_time_role_visible(self):
        """move$date with timeRole=business_date must appear in single-model markdown."""
        model = _make_payment_model()
        svc = _make_service_with(model)
        md = svc.get_metadata_v3_markdown(model_names=["OdooAccountPaymentModel"])
        assert "move$date" in md, "move$date field must be listed"
        assert "timeRole=business_date" in md, (
            "timeRole=business_date must be visible in the markdown output for move$date"
        )

    def test_join_property_recommended_use_visible(self):
        """recommendedUse for move$date must appear in single-model markdown."""
        model = _make_payment_model()
        svc = _make_service_with(model)
        md = svc.get_metadata_v3_markdown(model_names=["OdooAccountPaymentModel"])
        assert "recommendedUse=" in md, (
            "recommendedUse must be visible in the markdown output"
        )
        assert "payment trend" in md, "recommendedUse text must appear in markdown"

    def test_fact_column_time_role_visible(self):
        """Fact-table columns with timeRole must appear in single-model markdown."""
        model = _make_invoice_model()
        svc = _make_service_with(model)
        md = svc.get_metadata_v3_markdown(model_names=["OdooAccountMoveModel"])
        assert "invoice_date" in md
        assert "timeRole=business_date" in md, (
            "timeRole=business_date for invoice_date must appear in markdown"
        )
        assert "timeRole=posting_date" in md, (
            "timeRole=posting_date for date column must appear in markdown"
        )

    def test_column_without_time_role_unaffected(self):
        """Columns without timeRole must not show a spurious timeRole= token."""
        model = _make_invoice_model()
        svc = _make_service_with(model)
        md = svc.get_metadata_v3_markdown(model_names=["OdooAccountMoveModel"])
        # create_date has no timeRole — check it doesn't inject timeRole= near it
        lines = md.splitlines()
        for line in lines:
            if "create_date" in line:
                assert "timeRole=" not in line, (
                    f"create_date should not show timeRole= but found: {line!r}"
                )

    def test_markdown_table_cells_have_no_unescaped_pipes(self):
        """Pipe characters inside description/recommendedUse must be escaped."""
        # Build a prop with a pipe character in its recommendedUse
        prop_with_pipe = DimensionPropertyDef(
            column="date",
            name="date",
            caption="Date",
            data_type="DAY",
            timeRole="business_date",
            recommendedUse="Use for trend | period pivot queries.",
        )
        join = DimensionJoinDef(
            name="move",
            table_name="account_move",
            foreign_key="move_id",
            primary_key="id",
            caption_column="name",
            properties=[prop_with_pipe],
        )
        amount = DbModelMeasureImpl(
            name="amount", alias="Amount", column="amount",
            aggregation=AggregationType.SUM,
        )
        model = DbTableModelImpl(
            name="TestPipeModel", alias="Pipe Test", source_table="t",
            dimensions={}, measures={"amount": amount},
            columns={}, dimension_joins=[join],
        )
        svc = _make_service_with(model)
        md = svc.get_metadata_v3_markdown(model_names=["TestPipeModel"])
        # Each row in a markdown table is split by |; any | inside a cell
        # must have been replaced with the fullwidth ｜ (\uff5c)
        for line in md.splitlines():
            if "move$date" in line and "|" in line:
                # The line is a table row: split by | gives cells
                # There should be exactly the right number of pipes (table delimiters)
                # i.e. no extra raw | inside a cell value
                cells = line.split("|")
                for cell in cells[1:-1]:  # inner cells only
                    assert "|" not in cell, (
                        f"Unescaped pipe inside table cell: {line!r}"
                    )

    def test_multi_model_markdown_includes_time_role_hint(self):
        """Multi-model metadata listing must include timeRole hint for join properties."""
        model1 = _make_payment_model()
        model2 = _make_invoice_model()
        svc = SemanticQueryService()
        svc.register_model(model1)
        svc.register_model(model2)
        md = svc.get_metadata_v3_markdown()
        assert "timeRole=business_date" in md, (
            "timeRole=business_date must appear in multi-model metadata listing"
        )


# ---------------------------------------------------------------------------
# BUG-2 Tests: timeWindow field validation with property-level timeRole
# ---------------------------------------------------------------------------

class TestTimeWindowPropertyTimeRole:
    """BUG-2: property-level timeRole fields must be accepted by timeWindow validation."""

    def test_move_date_in_time_fields(self):
        """move$date with timeRole=business_date and DAY type must be in time_fields."""
        model = _make_payment_model()
        available, time_fields, measure_fields = collect_time_window_field_sets(model)
        assert "move$date" in available, "move$date must be in available_fields"
        assert "move$date" in time_fields, (
            "move$date with timeRole=business_date and DAY type must be in time_fields"
        )

    def test_move_company_id_not_in_time_fields(self):
        """move$companyId (INTEGER, no timeRole) must NOT be in time_fields."""
        model = _make_payment_model()
        _, time_fields, _ = collect_time_window_field_sets(model)
        assert "move$companyId" not in time_fields, (
            "move$companyId must not be added to time_fields"
        )

    def test_fact_column_with_time_role_in_time_fields(self):
        """Fact-table columns with timeRole=business_date and DATE type must be in time_fields."""
        model = _make_invoice_model()
        _, time_fields, _ = collect_time_window_field_sets(model)
        assert "invoice_date" in time_fields, (
            "invoice_date (timeRole=business_date, DATE) must be in time_fields"
        )
        assert "date" in time_fields, (
            "date (timeRole=posting_date, DATE) must be in time_fields"
        )

    def test_fact_column_without_time_role_not_in_time_fields(self):
        """create_date (no timeRole) must NOT be in time_fields even though it is DATETIME."""
        model = _make_invoice_model()
        _, time_fields, _ = collect_time_window_field_sets(model)
        assert "create_date" not in time_fields, (
            "create_date without timeRole must not be in time_fields"
        )

    def test_time_window_validator_accepts_move_date(self):
        """TimeWindowValidator.validate must pass when field=move$date.

        Uses comparison=rolling_30d / grain=day because yoy+month would also
        require move$date$month to be present (grain property check), which this
        minimal model doesn't have.  The key assertion is that move$date is
        accepted as a *time field*, not rejected as FIELD_NOT_TIME.
        """
        model = _make_payment_model()
        available, time_fields, measure_fields = collect_time_window_field_sets(model)
        tw = TimeWindowDef(
            field="move$date",
            grain="day",
            comparison="rolling_30d",
        )
        assert "move$date" in available
        result = TimeWindowValidator.validate(tw, available, time_fields, measure_fields)
        assert result is None, (
            f"Validation of move$date as timeWindow.field must pass but got: {result}"
        )

    def test_time_window_validator_rejects_synthetic_year_suffix(self):
        """move$date$year is a synthetic field and must fail FIELD_NOT_FOUND."""
        model = _make_payment_model()
        available, time_fields, measure_fields = collect_time_window_field_sets(model)
        tw = TimeWindowDef(
            field="move$date$year",
            grain="year",
            comparison="yoy",
        )
        result = TimeWindowValidator.validate(tw, available, time_fields, measure_fields)
        assert result == TimeWindowValidator.FIELD_NOT_FOUND, (
            f"move$date$year must fail FIELD_NOT_FOUND but got: {result}"
        )

    def test_time_window_validator_rejects_create_date(self):
        """createDate without timeRole must fail FIELD_NOT_TIME for timeWindow."""
        model = _make_invoice_model()
        available, time_fields, measure_fields = collect_time_window_field_sets(model)
        # Add create_date to available just to test the NOT_TIME path
        available.add("create_date")
        tw = TimeWindowDef(
            field="create_date",
            grain="month",
            comparison="yoy",
        )
        result = TimeWindowValidator.validate(tw, available, time_fields, measure_fields)
        assert result == TimeWindowValidator.FIELD_NOT_TIME, (
            f"create_date without timeRole must fail FIELD_NOT_TIME but got: {result}"
        )

    def test_time_window_validator_accepts_invoice_date(self):
        """invoice_date with timeRole=business_date and DATE type must pass validation."""
        model = _make_invoice_model()
        available, time_fields, measure_fields = collect_time_window_field_sets(model)
        tw = TimeWindowDef(
            field="invoice_date",
            grain="month",
            comparison="yoy",
        )
        result = TimeWindowValidator.validate(tw, available, time_fields, measure_fields)
        assert result is None, (
            f"invoice_date with timeRole=business_date must pass timeWindow validation but got: {result}"
        )
