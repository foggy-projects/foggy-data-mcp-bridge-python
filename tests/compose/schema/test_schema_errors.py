"""M4 · ComposeSchemaError + error_codes catalogue contract test."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.schema import (
    ComposeSchemaError,
    error_codes,
)


EXPECTED_CODES = {
    "compose-schema-error/derived-query/unknown-field",
    "compose-schema-error/column-spec/malformed",
    "compose-schema-error/duplicate-output-column",
    "compose-schema-error/union/column-count-mismatch",
    "compose-schema-error/join/on-left-unknown-field",
    "compose-schema-error/join/on-right-unknown-field",
    "compose-schema-error/join/output-column-conflict",
    # G10 PR2 — append two ambiguity-related codes.
    "compose-schema-error/output-schema/ambiguous-lookup",
    "compose-schema-error/join/ambiguous-column",
    # G10 PR4 — append three permission-validation codes; ALL_CODES = 12.
    "compose-schema-error/field-access/denied",
    "compose-schema-error/column/plan-not-bound",
    "compose-schema-error/column/field-not-found",
}


EXPECTED_PHASES = {
    "plan-build",
    "schema-derive",
    # G10 PR4 — plan-aware permission validation.
    "permission-validate",
}


class TestCatalogue:
    def test_all_codes_matches_expected(self):
        assert error_codes.ALL_CODES == frozenset(EXPECTED_CODES)
        assert len(error_codes.ALL_CODES) == 12

    def test_constants_expose_full_namespace(self):
        assert (
            error_codes.DERIVED_QUERY_UNKNOWN_FIELD
            == "compose-schema-error/derived-query/unknown-field"
        )
        assert (
            error_codes.UNION_COLUMN_COUNT_MISMATCH
            == "compose-schema-error/union/column-count-mismatch"
        )
        assert (
            error_codes.JOIN_OUTPUT_COLUMN_CONFLICT
            == "compose-schema-error/join/output-column-conflict"
        )

    def test_namespace_prefix_uniform(self):
        for code in error_codes.ALL_CODES:
            assert code.startswith(error_codes.NAMESPACE + "/")

    def test_valid_phases(self):
        assert error_codes.VALID_PHASES == frozenset(EXPECTED_PHASES)


class TestComposeSchemaErrorConstruction:
    def test_valid_construction(self):
        err = ComposeSchemaError(
            code=error_codes.DERIVED_QUERY_UNKNOWN_FIELD,
            message="unknown field 'foo'",
            plan_path="DerivedQueryPlan",
            offending_field="foo",
        )
        assert err.code == error_codes.DERIVED_QUERY_UNKNOWN_FIELD
        assert err.phase == "schema-derive"  # default
        assert err.plan_path == "DerivedQueryPlan"
        assert err.offending_field == "foo"

    def test_invalid_code_rejected(self):
        with pytest.raises(ValueError):
            ComposeSchemaError(
                code="compose-schema-error/made-up",
                message="x",
            )

    def test_invalid_phase_rejected(self):
        with pytest.raises(ValueError):
            ComposeSchemaError(
                code=error_codes.UNION_COLUMN_COUNT_MISMATCH,
                message="x",
                phase="runtime",
            )

    def test_cause_chain(self):
        original = RuntimeError("underlying")
        err = ComposeSchemaError(
            code=error_codes.COLUMN_SPEC_MALFORMED,
            message="malformed",
            phase="plan-build",
            cause=original,
        )
        assert err.__cause__ is original

    def test_repr_surfaces_diagnostic_fields(self):
        err = ComposeSchemaError(
            code=error_codes.JOIN_OUTPUT_COLUMN_CONFLICT,
            message="column conflict",
            plan_path="JoinPlan",
            offending_field="partnerName",
        )
        rep = repr(err)
        assert "ComposeSchemaError" in rep
        assert "JoinPlan" in rep
        assert "partnerName" in rep

    def test_all_7_codes_construct(self):
        for code in error_codes.ALL_CODES:
            err = ComposeSchemaError(code=code, message="x")
            assert err.code == code
