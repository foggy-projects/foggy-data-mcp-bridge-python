"""M1 AuthorityRequest / ModelQuery batch-contract test."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.context import Principal
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    ModelQuery,
)


@pytest.fixture
def principal() -> Principal:
    return Principal(user_id="u001", tenant_id="t001", roles=["admin"])


class TestModelQueryInvariants:
    def test_model_required_non_blank(self):
        with pytest.raises(ValueError):
            ModelQuery(model="", tables=["t1"])
        with pytest.raises(ValueError):
            ModelQuery(model=None, tables=[])  # type: ignore[arg-type]

    def test_tables_must_not_be_none(self):
        """None tables is rejected; empty list is legal."""
        with pytest.raises(TypeError):
            ModelQuery(model="SaleOrderQM", tables=None)  # type: ignore[arg-type]

    def test_empty_tables_is_legal(self):
        mq = ModelQuery(model="SaleOrderQM", tables=[])
        assert mq.tables == []

    def test_normal_construction(self):
        mq = ModelQuery(
            model="SaleOrderQM",
            tables=["sale_order", "sale_order_line"],
        )
        assert mq.model == "SaleOrderQM"
        assert mq.tables == ["sale_order", "sale_order_line"]


class TestAuthorityRequestBatchContract:
    def test_models_must_be_non_empty(self, principal):
        """Single-model requests use a size-1 list; empty is always illegal."""
        with pytest.raises(ValueError):
            AuthorityRequest(
                principal=principal,
                namespace="odoo",
                models=[],
            )

    def test_single_model_uses_size_one_list(self, principal):
        req = AuthorityRequest(
            principal=principal,
            namespace="odoo",
            models=[ModelQuery(model="SaleOrderQM", tables=["sale_order"])],
        )
        assert len(req.models) == 1
        assert req.model_names() == ["SaleOrderQM"]

    def test_multi_model_preserves_order(self, principal):
        req = AuthorityRequest(
            principal=principal,
            namespace="odoo",
            models=[
                ModelQuery(model="SaleOrderQM", tables=["sale_order"]),
                ModelQuery(model="CrmLeadQM", tables=["crm_lead"]),
                ModelQuery(model="ResPartnerQM", tables=["res_partner"]),
            ],
        )
        assert req.model_names() == ["SaleOrderQM", "CrmLeadQM", "ResPartnerQM"]

    def test_namespace_required(self, principal):
        with pytest.raises(ValueError):
            AuthorityRequest(
                principal=principal,
                namespace="",
                models=[ModelQuery(model="X", tables=[])],
            )

    def test_principal_type_checked(self):
        with pytest.raises(TypeError):
            AuthorityRequest(
                principal="u001",  # type: ignore[arg-type]
                namespace="odoo",
                models=[ModelQuery(model="X", tables=[])],
            )

    def test_models_entries_type_checked(self, principal):
        with pytest.raises(TypeError):
            AuthorityRequest(
                principal=principal,
                namespace="odoo",
                models=[{"model": "X", "tables": []}],  # type: ignore[list-item]
            )


class TestAuthorityRequestImmutability:
    def test_frozen(self, principal):
        req = AuthorityRequest(
            principal=principal,
            namespace="odoo",
            models=[ModelQuery(model="X", tables=[])],
        )
        with pytest.raises(Exception):
            req.namespace = "other"  # type: ignore[misc]
