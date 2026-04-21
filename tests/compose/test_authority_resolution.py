"""M1 AuthorityResolution / ModelBinding contract test."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)
from foggy.mcp_spi.semantic import DeniedColumn


class TestModelBindingFieldAccessSemantics:
    """field_access: None means "no allowlist"; [] means "all blocked"."""

    def test_field_access_none_is_legal(self):
        """Odoo Pro v1 default — rely on deniedColumns."""
        b = ModelBinding(field_access=None)
        assert b.field_access is None
        assert b.denied_columns == []
        assert b.system_slice == []

    def test_field_access_empty_list_is_distinct_from_none(self):
        """Pathological-but-legal: every field is blocked."""
        b = ModelBinding(field_access=[])
        assert b.field_access == []
        assert b.field_access is not None

    def test_field_access_whitelist(self):
        b = ModelBinding(field_access=["partner$id", "partner$caption"])
        assert b.field_access == ["partner$id", "partner$caption"]


class TestModelBindingCollectionsNonNull:
    def test_denied_columns_must_not_be_none(self):
        with pytest.raises(TypeError):
            ModelBinding(denied_columns=None)  # type: ignore[arg-type]

    def test_system_slice_must_not_be_none(self):
        with pytest.raises(TypeError):
            ModelBinding(system_slice=None)  # type: ignore[arg-type]

    def test_populated_denied_columns(self):
        b = ModelBinding(
            denied_columns=[
                DeniedColumn(table="sale_order", column="internal_cost"),
            ],
        )
        assert len(b.denied_columns) == 1
        assert b.denied_columns[0].table == "sale_order"

    def test_populated_system_slice(self):
        """system_slice accepts plain dicts (v1.3 shape)."""
        b = ModelBinding(
            system_slice=[
                {"field": "orgId", "op": "=", "value": "org001"},
                {"field": "deptId", "op": "=", "value": "d1"},
            ],
        )
        assert len(b.system_slice) == 2
        assert b.system_slice[0]["field"] == "orgId"


class TestAuthorityResolutionContract:
    def test_empty_bindings_dict_is_constructible(self):
        """Construction does not enforce non-empty; callers enforce the
        request-vs-response key-set invariant at the resolver boundary."""
        r = AuthorityResolution(bindings={})
        assert r.bindings == {}

    def test_bindings_keyed_by_model_name(self):
        r = AuthorityResolution(
            bindings={
                "SaleOrderQM": ModelBinding(),
                "CrmLeadQM": ModelBinding(
                    denied_columns=[
                        DeniedColumn(table="crm_lead", column="source_cost"),
                    ],
                ),
            },
        )
        assert set(r.bindings.keys()) == {"SaleOrderQM", "CrmLeadQM"}
        assert r.bindings["CrmLeadQM"].denied_columns[0].column == "source_cost"

    def test_bindings_keys_must_be_non_blank_string(self):
        with pytest.raises(ValueError):
            AuthorityResolution(bindings={"": ModelBinding()})

    def test_bindings_values_must_be_ModelBinding(self):
        with pytest.raises(TypeError):
            AuthorityResolution(
                bindings={"SaleOrderQM": {"field_access": None}},  # type: ignore[dict-item]
            )

    def test_bindings_must_not_be_none(self):
        with pytest.raises(TypeError):
            AuthorityResolution(bindings=None)  # type: ignore[arg-type]


class TestImmutability:
    def test_model_binding_frozen(self):
        b = ModelBinding()
        with pytest.raises(Exception):
            b.field_access = ["x"]  # type: ignore[misc]

    def test_authority_resolution_frozen(self):
        r = AuthorityResolution(bindings={})
        with pytest.raises(Exception):
            r.bindings = {"x": ModelBinding()}  # type: ignore[misc]
