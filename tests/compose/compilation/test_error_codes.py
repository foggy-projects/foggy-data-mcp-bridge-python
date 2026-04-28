"""Guard tests for the M6 error-code contract.

The spec §验收硬门槛 #3 requires:
  - ``NAMESPACE == "compose-compile-error"`` (prefix constant)
  - Exactly 4 ``compose-compile-error/*`` codes registered in ALL_CODES
  - ``ComposeCompileError`` rejects construction with an unknown code
    or phase (fail-closed)
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    ComposeCompileError,
    error_codes,
)


class TestNamespaceAndCodes:
    def test_namespace_is_literal(self):
        assert error_codes.NAMESPACE == "compose-compile-error"

    def test_all_codes_count(self):
        # NAMESPACE is NOT in ALL_CODES by design
        assert len(error_codes.ALL_CODES) == 7

    def test_all_codes_literal_strings(self):
        assert error_codes.UNSUPPORTED_PLAN_SHAPE == "compose-compile-error/unsupported-plan-shape"
        assert error_codes.CROSS_DATASOURCE_REJECTED == "compose-compile-error/cross-datasource-rejected"
        assert error_codes.MISSING_BINDING == "compose-compile-error/missing-binding"
        assert error_codes.PER_BASE_COMPILE_FAILED == "compose-compile-error/per-base-compile-failed"

    def test_all_codes_share_namespace_prefix(self):
        for code in error_codes.ALL_CODES:
            assert code.startswith(error_codes.NAMESPACE + "/"), (
                f"Code {code!r} must start with {error_codes.NAMESPACE}/"
            )

    def test_all_codes_are_registered(self):
        assert error_codes.is_valid_code(error_codes.UNSUPPORTED_PLAN_SHAPE)
        assert error_codes.is_valid_code(error_codes.CROSS_DATASOURCE_REJECTED)
        assert error_codes.is_valid_code(error_codes.MISSING_BINDING)
        assert error_codes.is_valid_code(error_codes.PER_BASE_COMPILE_FAILED)

    def test_unknown_code_rejected(self):
        assert not error_codes.is_valid_code("compose-compile-error/bogus")
        # NAMESPACE alone is NOT a valid code
        assert not error_codes.is_valid_code(error_codes.NAMESPACE)


class TestPhases:
    def test_phases_count(self):
        assert len(error_codes.VALID_PHASES) == 2

    def test_phase_literals(self):
        assert error_codes.is_valid_phase("plan-lower")
        assert error_codes.is_valid_phase("compile")

    def test_unknown_phase_rejected(self):
        assert not error_codes.is_valid_phase("runtime")
        assert not error_codes.is_valid_phase("")


class TestComposeCompileErrorConstruction:
    def test_happy_path(self):
        err = ComposeCompileError(
            code=error_codes.MISSING_BINDING,
            phase="plan-lower",
            message="no binding",
        )
        assert err.code == error_codes.MISSING_BINDING
        assert err.phase == "plan-lower"
        assert err.message == "no binding"
        assert "[compose-compile-error/missing-binding]" in str(err)
        assert "(plan-lower)" in str(err)
        assert "no binding" in str(err)

    def test_reject_unknown_code(self):
        with pytest.raises(ValueError, match="Invalid ComposeCompileError code"):
            ComposeCompileError(
                code="compose-compile-error/typo",
                phase="compile",
                message="x",
            )

    def test_reject_namespace_as_code(self):
        """NAMESPACE is a prefix, never a standalone code."""
        with pytest.raises(ValueError, match="Invalid ComposeCompileError code"):
            ComposeCompileError(
                code=error_codes.NAMESPACE,
                phase="compile",
                message="x",
            )

    def test_reject_unknown_phase(self):
        with pytest.raises(ValueError, match="Invalid ComposeCompileError phase"):
            ComposeCompileError(
                code=error_codes.MISSING_BINDING,
                phase="runtime",
                message="x",
            )

    def test_cause_chain_preserved(self):
        """``raise ... from exc`` keeps __cause__ — critical for D1."""
        original = RuntimeError("v1.3 engine failure")
        try:
            try:
                raise original
            except RuntimeError as exc:
                raise ComposeCompileError(
                    code=error_codes.PER_BASE_COMPILE_FAILED,
                    phase="compile",
                    message="wrapped",
                ) from exc
        except ComposeCompileError as final:
            assert final.__cause__ is original


class TestExportSurface:
    """The public ``__init__`` must re-export only the 3 documented names."""

    def test_public_exports(self):
        from foggy.dataset_model.engine.compose import compilation

        expected = {"compile_plan_to_sql", "ComposeCompileError", "error_codes"}
        assert set(compilation.__all__) == expected
        # (Submodules ``per_base`` / ``compose_planner`` / ``plan_hash`` are
        # loaded as import side-effects of ``compiler.py`` — that's unavoidable
        # Python behaviour. The ``__all__`` contract above is the real
        # public surface; ``from compilation import *`` will NOT pull them in.)
