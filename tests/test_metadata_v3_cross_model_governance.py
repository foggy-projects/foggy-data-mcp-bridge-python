# -*- coding: utf-8 -*-
"""F-3 regression: _resolve_effective_visible cross-model denied QM-field leak.

Tracks: foggy-data-mcp-bridge-python/docs/v1.6/P0-BUG-F3-resolve-effective-visible-cross-model-denied-leak-需求.md
Upstream bug workitem: foggy-odoo-bridge-pro/docs/prompts/v1.4/workitems/BUG-v14-metadata-v3-denied-columns-cross-model-leak.md

Scenario: Multiple QM models share the same QM field name (e.g. `name`) but those
QM fields map to different physical columns (e.g. `sale_order.name` vs
`res_partner.name`). A DeniedColumn targeting one model's physical column must
NOT strip the shared QM field name from OTHER models.

Before fix (buggy): denying `sale_order.name` strips `name` globally because
`_resolve_effective_visible` merges denied QM fields across models into a flat
set, losing model attribution.

After fix: `_resolve_effective_visible` returns `Optional[Dict[str, Set[str]]]`,
one effective set per model, and `get_metadata_v3` filters `fields[x]['models']`
per-model instead of dropping the top-level key.
"""

import pytest

from foggy.dataset_model.definitions.base import ColumnType
from foggy.dataset_model.impl.model import DbModelDimensionImpl, DbTableModelImpl
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi.semantic import DeniedColumn


# ============================================================================
# Fixtures
# ============================================================================


def _make_model(name, table):
    """Minimal two-dimension model used across the F-3 scenarios.

    Shared dimension names (`name`, `amountTotal`, `company`) intentionally
    mirror the Odoo Pro repro case so this file and the Odoo Pro xfail case
    describe the same invariants.
    """
    return DbTableModelImpl(
        name=name,
        source_table=table,
        dimensions={
            "name": DbModelDimensionImpl(
                name="name",
                column="name",
                data_type=ColumnType.STRING,
            ),
            "amountTotal": DbModelDimensionImpl(
                name="amountTotal",
                column="amount_total",
                data_type=ColumnType.DECIMAL,
            ),
            "company": DbModelDimensionImpl(
                name="company",
                column="company_id",
                data_type=ColumnType.INTEGER,
            ),
        },
        measures={},
        dimension_joins=[],
    )


@pytest.fixture
def two_model_service():
    service = SemanticQueryService()
    service.register_model(_make_model("SaleModel", "sale_order"))
    service.register_model(_make_model("PartnerModel", "res_partner"))
    return service


# ============================================================================
# F-3 Regression: the core failing case
# ============================================================================


class TestF3Regression:
    """Primary F-3 regression — mirrors the Odoo Pro xfailed case verbatim."""

    def test_denied_on_one_model_does_not_strip_shared_field_from_another(
        self, two_model_service
    ):
        """DeniedColumn(table='sale_order', column='name') must only strip
        SaleModel's `name` attribution, not PartnerModel's.
        """
        metadata = two_model_service.get_metadata_v3(
            model_names=["SaleModel", "PartnerModel"],
            denied_columns=[DeniedColumn(table="sale_order", column="name")],
        )

        name_entry = metadata["fields"].get("name")
        assert name_entry is not None, (
            "Shared QM field 'name' must remain visible because PartnerModel "
            "maps it to res_partner.name which was NOT denied"
        )
        assert set(name_entry["models"].keys()) == {"PartnerModel"}, (
            "Only PartnerModel should retain 'name'. Got: "
            f"{list(name_entry['models'].keys())}"
        )


# ============================================================================
# Positive cases — verify non-leaky governance behaviour
# ============================================================================


class TestCrossModelGovernancePositive:
    def test_shared_field_both_allowed_when_no_deny(self, two_model_service):
        """No denied_columns → both models keep the shared 'name' attribution."""
        metadata = two_model_service.get_metadata_v3(
            model_names=["SaleModel", "PartnerModel"],
        )
        name_entry = metadata["fields"].get("name")
        assert name_entry is not None
        assert set(name_entry["models"].keys()) == {"SaleModel", "PartnerModel"}

    def test_denied_on_both_models_strips_shared_field_entirely(self, two_model_service):
        """Deny both models' physical 'name' columns → the shared QM field
        disappears from metadata entirely (no surviving model attribution)."""
        metadata = two_model_service.get_metadata_v3(
            model_names=["SaleModel", "PartnerModel"],
            denied_columns=[
                DeniedColumn(table="sale_order", column="name"),
                DeniedColumn(table="res_partner", column="name"),
            ],
        )
        assert "name" not in metadata["fields"]
        # Other shared fields should still be there (e.g. amountTotal)
        amount_entry = metadata["fields"].get("amountTotal")
        assert amount_entry is not None
        assert set(amount_entry["models"].keys()) == {"SaleModel", "PartnerModel"}

    def test_visible_fields_whitelist_applies_per_model(self, two_model_service):
        """visible_fields=['name'] + deny SaleModel's name → only PartnerModel
        retains 'name' (since SaleModel's name is denied but still in whitelist)."""
        metadata = two_model_service.get_metadata_v3(
            model_names=["SaleModel", "PartnerModel"],
            visible_fields=["name"],
            denied_columns=[DeniedColumn(table="sale_order", column="name")],
        )
        name_entry = metadata["fields"].get("name")
        assert name_entry is not None
        assert set(name_entry["models"].keys()) == {"PartnerModel"}

        # amountTotal not in whitelist → should be dropped from metadata entirely
        assert "amountTotal" not in metadata["fields"]
        assert "company" not in metadata["fields"]

    def test_denied_column_on_unshared_field_leaves_other_models_untouched(
        self, two_model_service
    ):
        """Deny an amountTotal column on SaleModel only → PartnerModel's
        amountTotal remains fully visible."""
        metadata = two_model_service.get_metadata_v3(
            model_names=["SaleModel", "PartnerModel"],
            denied_columns=[DeniedColumn(table="sale_order", column="amount_total")],
        )
        amount_entry = metadata["fields"].get("amountTotal")
        assert amount_entry is not None
        assert set(amount_entry["models"].keys()) == {"PartnerModel"}

    def test_empty_denied_list_no_op(self, two_model_service):
        """denied_columns=[] with no visible_fields → returns None effective,
        every field keeps full model attribution."""
        metadata = two_model_service.get_metadata_v3(
            model_names=["SaleModel", "PartnerModel"],
            denied_columns=[],
        )
        name_entry = metadata["fields"].get("name")
        assert name_entry is not None
        assert set(name_entry["models"].keys()) == {"SaleModel", "PartnerModel"}


# ============================================================================
# Markdown path — signature compatibility smoke test
# ============================================================================


class TestMarkdownCrossModelGovernance:
    """Smoke test for the markdown builder's new per_model_visible signature.

    Content-level assertions for markdown trimming live in
    `test_physical_column_governance.py::TestMetadataDeniedColumnsTrimming`.
    """

    def test_markdown_multi_model_with_deny_does_not_crash(self, two_model_service):
        """v1.6 F-3 changed `_build_multi_model_markdown` signature to accept
        `per_model_visible`; verify the caller wires it through correctly and
        no TypeError/KeyError leaks."""
        md = two_model_service.get_metadata_v3_markdown(
            model_names=["SaleModel", "PartnerModel"],
            denied_columns=[DeniedColumn(table="sale_order", column="name")],
        )
        # Must render both model section headers
        assert "SaleModel" in md
        assert "PartnerModel" in md
