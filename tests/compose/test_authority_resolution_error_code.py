"""M1 AuthorityResolutionError code-enum parity test.

Cross-repo invariant (see M1-AuthorityResolver-SPI签名冻结-需求.md):
    Java `AuthorityErrorCodes.java` and Python `error_codes.py` must expose
    the same seven code strings, character-for-character.

This test acts as the Python-side half of that parity contract; the Java
test (``AuthorityResolutionErrorCodeTest``) asserts the mirror image.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.security import error_codes
from foggy.dataset_model.engine.compose.security.exceptions import (
    AuthorityResolutionError,
)


# ---------------------------------------------------------------------------
# The seven frozen codes (M1 contract)
# ---------------------------------------------------------------------------

EXPECTED_CODES = {
    "compose-authority-resolve/resolver-not-available",
    "compose-authority-resolve/model-binding-missing",
    "compose-authority-resolve/model-not-mapped",
    "compose-authority-resolve/principal-mismatch",
    "compose-authority-resolve/upstream-failure",
    "compose-authority-resolve/invalid-response",
    "compose-authority-resolve/ir-rule-unmapped-field",
}


EXPECTED_PHASES = {
    "authority-resolve",
    "schema-derive",
    "compile",
    "execute",
    "script-parse",
    "script-eval",
    "plan-build",
}


class TestErrorCodesCatalogue:
    def test_all_codes_set_matches_expected(self):
        assert error_codes.ALL_CODES == frozenset(EXPECTED_CODES)

    def test_each_code_constant_present(self):
        """Individual constants exist at the documented names."""
        assert (
            error_codes.RESOLVER_NOT_AVAILABLE
            == "compose-authority-resolve/resolver-not-available"
        )
        assert (
            error_codes.MODEL_BINDING_MISSING
            == "compose-authority-resolve/model-binding-missing"
        )
        assert (
            error_codes.MODEL_NOT_MAPPED
            == "compose-authority-resolve/model-not-mapped"
        )
        assert (
            error_codes.PRINCIPAL_MISMATCH
            == "compose-authority-resolve/principal-mismatch"
        )
        assert (
            error_codes.UPSTREAM_FAILURE
            == "compose-authority-resolve/upstream-failure"
        )
        assert (
            error_codes.INVALID_RESPONSE
            == "compose-authority-resolve/invalid-response"
        )
        assert (
            error_codes.IR_RULE_UNMAPPED_FIELD
            == "compose-authority-resolve/ir-rule-unmapped-field"
        )

    def test_namespace_prefix_on_every_code(self):
        """Every code string must start with the namespace prefix."""
        for code in error_codes.ALL_CODES:
            assert code.startswith(error_codes.NAMESPACE + "/"), (
                f"code {code!r} missing namespace prefix {error_codes.NAMESPACE!r}"
            )

    def test_valid_phases_set_matches_expected(self):
        assert error_codes.VALID_PHASES == frozenset(EXPECTED_PHASES)


class TestAuthorityResolutionErrorConstruction:
    def test_valid_construction_records_code_and_phase(self):
        err = AuthorityResolutionError(
            code=error_codes.UPSTREAM_FAILURE,
            message="upstream offline",
            model_involved="SaleOrderQM",
        )
        assert err.code == error_codes.UPSTREAM_FAILURE
        assert err.model_involved == "SaleOrderQM"
        assert err.phase == error_codes.PHASE_AUTHORITY_RESOLVE
        assert str(err) == "upstream offline"

    def test_invalid_code_rejected(self):
        with pytest.raises(ValueError):
            AuthorityResolutionError(
                code="made-up/not-in-catalogue",
                message="x",
            )

    def test_invalid_phase_rejected(self):
        with pytest.raises(ValueError):
            AuthorityResolutionError(
                code=error_codes.UPSTREAM_FAILURE,
                message="x",
                phase="made-up-phase",
            )

    def test_cause_attached_via_ctor(self):
        original = RuntimeError("network")
        err = AuthorityResolutionError(
            code=error_codes.UPSTREAM_FAILURE,
            message="http 503",
            cause=original,
        )
        assert err.__cause__ is original

    def test_default_phase_is_authority_resolve(self):
        err = AuthorityResolutionError(
            code=error_codes.MODEL_BINDING_MISSING,
            message="missing",
        )
        assert err.phase == "authority-resolve"

    def test_all_seven_codes_accepted(self):
        """Every ALL_CODES entry can construct an error without validation raising."""
        for code in error_codes.ALL_CODES:
            err = AuthorityResolutionError(code=code, message="x")
            assert err.code == code

    def test_repr_is_helpful_for_debugging(self):
        err = AuthorityResolutionError(
            code=error_codes.MODEL_NOT_MAPPED,
            message="no mapping for SaleOrderQM",
            model_involved="SaleOrderQM",
        )
        rep = repr(err)
        assert "AuthorityResolutionError" in rep
        assert error_codes.MODEL_NOT_MAPPED in rep
        assert "SaleOrderQM" in rep
