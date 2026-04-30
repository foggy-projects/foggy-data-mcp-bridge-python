"""Unit tests for ``AuthorityBindingResolver`` — Odoo remote binding adapter.

These tests validate the resolver in isolation (no MCP tool pipeline, no
ComposeQueryContext, no SemanticQueryService). They mirror the Java-side
``AuthorityBindingResolverTest`` and additionally cover the P1/P2 fixes:

- Constructor-time envelope validation
- systemSlice structural parsing ($or / $and / $expr / leaf)
- fieldAccess item-level non-blank validation
- Tenant dual-source diverge detection
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from foggy.dataset_model.engine.compose.authority.binding_resolver import (
    AuthorityBindingResolver,
    VERSION,
    ISSUER_ODOO_BRIDGE,
    ISSUER_TEST_FIXTURE,
)
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolutionError,
    ModelQuery,
    error_codes,
)
from foggy.dataset_model.engine.compose.context.principal import Principal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _valid_envelope(**overrides: Any) -> Dict[str, Any]:
    """Build a structurally valid envelope, allowing field overrides."""
    env: Dict[str, Any] = {
        "version": VERSION,
        "issuer": ISSUER_TEST_FIXTURE,
        "namespace": "odoo",
        "tenantId": "t1",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "SalesQM": {
                "fieldAccess": ["amount"],
                "deniedColumns": [
                    {"schema": " ", "table": " fact_sales ", "column": " secret_amount "}
                ],
                "systemSlice": [
                    {"field": "customer_key", "op": "=", "value": 42}
                ],
            }
        },
    }
    env.update(overrides)
    return env


def _request(
    user_id: str = "u1",
    tenant_id: str = "t1",
    namespace: str = "odoo",
    model: str = "SalesQM",
) -> AuthorityRequest:
    return AuthorityRequest(
        principal=Principal(user_id=user_id, tenant_id=tenant_id),
        namespace=namespace,
        models=[ModelQuery(model=model, tables=["fact_sales"])],
    )


# ---------------------------------------------------------------------------
# Constructor-time validation (P1)
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """P1: envelope validation happens at construction time."""

    def test_construction_rejects_non_dict_envelope(self):
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver("not-a-dict", "odoo")
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_construction_rejects_invalid_version(self):
        env = _valid_envelope(version="bad-version")
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo")
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "version" in str(exc_info.value).lower()

    def test_construction_rejects_invalid_issuer(self):
        env = _valid_envelope(issuer="unknown-issuer")
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo")
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "issuer" in str(exc_info.value).lower()

    def test_construction_rejects_namespace_mismatch(self):
        env = _valid_envelope(namespace="wrong-ns")
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo")
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "namespace" in str(exc_info.value).lower()

    def test_construction_rejects_missing_principal(self):
        env = _valid_envelope(principal="not-a-dict")
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo")
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "principal" in str(exc_info.value).lower()

    def test_construction_rejects_non_dict_bindings(self):
        env = _valid_envelope(bindings="not-a-dict")
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo")
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "bindings" in str(exc_info.value).lower()

    def test_construction_accepts_valid_envelope(self):
        """Valid envelope should not raise — resolver instance is created."""
        resolver = AuthorityBindingResolver(_valid_envelope(), "odoo")
        assert resolver is not None

    def test_both_allowed_issuers_accepted(self):
        """Both foggy-odoo-bridge-pro and test-fixture-issuer are valid."""
        AuthorityBindingResolver(
            _valid_envelope(issuer=ISSUER_ODOO_BRIDGE), "odoo"
        )
        AuthorityBindingResolver(
            _valid_envelope(issuer=ISSUER_TEST_FIXTURE), "odoo"
        )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:

    def test_valid_binding_parses_native_model_binding(self):
        resolution = AuthorityBindingResolver(
            _valid_envelope(), "odoo"
        ).resolve(_request())

        binding = resolution.bindings["SalesQM"]
        assert binding.field_access == ["amount"]
        assert len(binding.denied_columns) == 1
        assert binding.denied_columns[0].schema_name is None  # whitespace → None
        assert binding.denied_columns[0].table == "fact_sales"
        assert binding.denied_columns[0].column == "secret_amount"
        assert len(binding.system_slice) == 1
        assert binding.system_slice[0]["field"] == "customer_key"
        assert binding.system_slice[0]["op"] == "="
        assert binding.system_slice[0]["value"] == 42

    def test_null_field_access_preserved(self):
        """fieldAccess=None means no whitelist; should not become []."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["fieldAccess"] = None
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert resolution.bindings["SalesQM"].field_access is None

    def test_empty_field_access_preserved(self):
        """fieldAccess=[] means 'no field visible' — distinct from None."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["fieldAccess"] = []
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert resolution.bindings["SalesQM"].field_access == []


# ---------------------------------------------------------------------------
# Model binding missing
# ---------------------------------------------------------------------------


class TestModelBindingMissing:

    def test_missing_model_binding_fails_closed(self):
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(_valid_envelope(), "odoo").resolve(
                _request(model="OtherQM")
            )
        assert exc_info.value.code == error_codes.MODEL_BINDING_MISSING
        assert exc_info.value.model_involved == "OtherQM"


# ---------------------------------------------------------------------------
# Principal / tenant validation
# ---------------------------------------------------------------------------


class TestIdentityValidation:

    def test_principal_mismatch_fails_closed(self):
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(_valid_envelope(), "odoo").resolve(
                _request(user_id="u2")
            )
        assert exc_info.value.code == error_codes.PRINCIPAL_MISMATCH

    def test_tenant_mismatch_fails_closed(self):
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(_valid_envelope(), "odoo").resolve(
                _request(tenant_id="t2")
            )
        assert exc_info.value.code == error_codes.PRINCIPAL_MISMATCH

    def test_namespace_mismatch_in_resolve_fails_closed(self):
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(_valid_envelope(), "odoo").resolve(
                _request(namespace="default")
            )
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_tenant_diverge_between_principal_and_envelope_fails(self):
        """P2: principal.tenantId != envelope.tenantId → diverge error."""
        env = _valid_envelope()
        env["tenantId"] = "t1"
        env["principal"]["tenantId"] = "t-different"
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.PRINCIPAL_MISMATCH
        assert "diverge" in str(exc_info.value).lower()

    def test_tenant_none_in_envelope_uses_principal_tenant(self):
        """When envelope-level tenantId is absent, principal.tenantId is used."""
        env = _valid_envelope()
        del env["tenantId"]  # only principal.tenantId remains
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert "SalesQM" in resolution.bindings


# ---------------------------------------------------------------------------
# deniedColumns validation
# ---------------------------------------------------------------------------


class TestDeniedColumnsValidation:

    def test_malformed_denied_columns_array_fails_closed(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["deniedColumns"] = {
            "table": "fact_sales", "column": "secret_amount"
        }
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_empty_denied_column_table_fails_closed(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["deniedColumns"] = [
            {"table": "   ", "column": "secret_amount"}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_empty_denied_column_column_fails_closed(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["deniedColumns"] = [
            {"table": "fact_sales", "column": "   "}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_denied_column_missing_keys_fails_closed(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["deniedColumns"] = [{"table": "fact_sales"}]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE


# ---------------------------------------------------------------------------
# fieldAccess validation (P2)
# ---------------------------------------------------------------------------


class TestFieldAccessValidation:

    def test_field_access_blank_item_fails_closed(self):
        """P2: fieldAccess containing a whitespace-only string is invalid."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["fieldAccess"] = ["amount", "   "]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "fieldaccess" in str(exc_info.value).lower()

    def test_field_access_non_string_item_fails_closed(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["fieldAccess"] = ["amount", 123]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_field_access_non_list_fails_closed(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["fieldAccess"] = "amount"
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE


# ---------------------------------------------------------------------------
# systemSlice validation (P1)
# ---------------------------------------------------------------------------


class TestSystemSliceValidation:

    def test_system_slice_non_dict_item_fails_closed(self):
        """P1: each systemSlice entry must be a dict."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = ["not-a-dict"]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE
        assert "systemslice" in str(exc_info.value).lower()

    def test_system_slice_missing_field_fails_closed(self):
        """P1: leaf condition without 'field' is rejected."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"op": "=", "value": 42}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_system_slice_missing_op_fails_closed(self):
        """P1: leaf condition without 'op' or 'type' is rejected."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"field": "customer_key", "value": 42}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_system_slice_type_alias_for_op(self):
        """'type' is accepted as alias for 'op' (mirrors Java readEither)."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"field": "customer_key", "type": "eq", "value": 42}
        ]
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert len(resolution.bindings["SalesQM"].system_slice) == 1

    def test_system_slice_logical_or_group(self):
        """P1: $or must contain a list of valid conditions."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {
                "$or": [
                    {"field": "region", "op": "=", "value": "EU"},
                    {"field": "region", "op": "=", "value": "US"},
                ]
            }
        ]
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert len(resolution.bindings["SalesQM"].system_slice) == 1

    def test_system_slice_logical_and_group(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {
                "$and": [
                    {"field": "region", "op": "=", "value": "EU"},
                    {"field": "status", "op": "=", "value": "active"},
                ]
            }
        ]
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert len(resolution.bindings["SalesQM"].system_slice) == 1

    def test_system_slice_or_non_list_fails(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"$or": "not-a-list"}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_system_slice_expr_parsed(self):
        """P1: $expr must be a non-blank string."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"$expr": "customer_key IN (SELECT id FROM vip)"}
        ]
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert len(resolution.bindings["SalesQM"].system_slice) == 1

    def test_system_slice_expr_blank_fails(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"$expr": "   "}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_system_slice_max_depth_non_numeric_fails(self):
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = [
            {"field": "org_id", "op": "=", "value": 1, "maxDepth": "three"}
        ]
        with pytest.raises(AuthorityResolutionError) as exc_info:
            AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert exc_info.value.code == error_codes.INVALID_RESPONSE

    def test_system_slice_empty_list_accepted(self):
        """Empty systemSlice is legal (no row-level restrictions)."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = []
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert resolution.bindings["SalesQM"].system_slice == []

    def test_system_slice_null_accepted(self):
        """null systemSlice defaults to empty list."""
        env = _valid_envelope()
        env["bindings"]["SalesQM"]["systemSlice"] = None
        resolution = AuthorityBindingResolver(env, "odoo").resolve(_request())
        assert resolution.bindings["SalesQM"].system_slice == []
