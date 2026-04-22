"""M3 · ComposeSandboxViolation 14 错误码 + phase 枚举 parity 契约测试.

Cross-repo invariant: 这 14 个 code 字符串必须与 Java
``ComposeSandboxErrorCodes.java`` 逐字符对齐；`M9-三层沙箱防护测试脚手架.md`
的用例断言也引用这些常量。
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.sandbox import error_codes
from foggy.dataset_model.engine.compose.sandbox.exceptions import (
    ComposeSandboxViolationError,
)


# ---------------------------------------------------------------------------
# Expected frozen catalogue — kept in a literal set so parity with the
# sandbox scaffold doc is visually obvious.
# ---------------------------------------------------------------------------


EXPECTED_CODES = {
    # Layer A — 8 codes
    "compose-sandbox-violation/A/eval-denied",
    "compose-sandbox-violation/A/async-denied",
    "compose-sandbox-violation/A/network-denied",
    "compose-sandbox-violation/A/io-denied",
    "compose-sandbox-violation/A/global-denied",
    "compose-sandbox-violation/A/time-denied",
    "compose-sandbox-violation/A/security-param-denied",
    "compose-sandbox-violation/A/context-access-denied",
    # Layer B — 3 codes
    "compose-sandbox-violation/B/function-denied",
    "compose-sandbox-violation/B/derived-plan-function-denied",
    "compose-sandbox-violation/B/injection-suspected",
    # Layer C — 3 codes
    "compose-sandbox-violation/C/method-denied",
    "compose-sandbox-violation/C/result-iteration-denied",
    "compose-sandbox-violation/C/cross-datasource-denied",
}


EXPECTED_PHASES = {
    "script-parse",
    "script-eval",
    "plan-build",
    "schema-derive",
    "authority-resolve",
    "compile",
    "execute",
}


class TestCatalogue:
    def test_all_codes_set_matches_expected(self):
        assert error_codes.ALL_CODES == frozenset(EXPECTED_CODES)
        assert len(error_codes.ALL_CODES) == 14, "三层白名单共 14 个 violation code"

    def test_each_constant_name_resolves(self):
        """Individual Python constants exist at the documented names."""
        assert (
            error_codes.LAYER_A_EVAL_DENIED
            == "compose-sandbox-violation/A/eval-denied"
        )
        assert (
            error_codes.LAYER_A_CONTEXT_ACCESS
            == "compose-sandbox-violation/A/context-access-denied"
        )
        assert (
            error_codes.LAYER_B_INJECTION_SUSPECTED
            == "compose-sandbox-violation/B/injection-suspected"
        )
        assert (
            error_codes.LAYER_C_CROSS_DS
            == "compose-sandbox-violation/C/cross-datasource-denied"
        )

    def test_namespace_prefix_on_every_code(self):
        for code in error_codes.ALL_CODES:
            assert code.startswith(error_codes.NAMESPACE + "/"), code

    def test_layer_counts(self):
        layer_a = [c for c in error_codes.ALL_CODES if "/A/" in c]
        layer_b = [c for c in error_codes.ALL_CODES if "/B/" in c]
        layer_c = [c for c in error_codes.ALL_CODES if "/C/" in c]
        assert len(layer_a) == 8
        assert len(layer_b) == 3
        assert len(layer_c) == 3

    def test_valid_phases_set_matches_expected(self):
        assert error_codes.VALID_PHASES == frozenset(EXPECTED_PHASES)


class TestLayerKindHelpers:
    def test_layer_of_returns_single_letter(self):
        assert error_codes.layer_of(error_codes.LAYER_A_EVAL_DENIED) == "A"
        assert error_codes.layer_of(error_codes.LAYER_B_FUNCTION_DENIED) == "B"
        assert error_codes.layer_of(error_codes.LAYER_C_METHOD_DENIED) == "C"

    def test_layer_of_raises_for_unknown_code(self):
        with pytest.raises(ValueError):
            error_codes.layer_of("totally-made-up/namespace")

    def test_kind_of_returns_trailing_segment(self):
        assert error_codes.kind_of(error_codes.LAYER_A_EVAL_DENIED) == "eval-denied"
        assert (
            error_codes.kind_of(error_codes.LAYER_B_INJECTION_SUSPECTED)
            == "injection-suspected"
        )


# ---------------------------------------------------------------------------
# Exception construction contract
# ---------------------------------------------------------------------------


class TestComposeSandboxViolationErrorConstruction:
    def test_valid_construction_records_fields(self):
        err = ComposeSandboxViolationError(
            code=error_codes.LAYER_A_EVAL_DENIED,
            message="Dynamic evaluation is not allowed in compose scripts.",
            phase=error_codes.PHASE_SCRIPT_EVAL,
        )
        assert err.code == error_codes.LAYER_A_EVAL_DENIED
        assert err.layer == "A"
        assert err.kind == "eval-denied"
        assert err.phase == "script-eval"
        assert err.script_location is None

    def test_invalid_code_rejected(self):
        with pytest.raises(ValueError):
            ComposeSandboxViolationError(
                code="made-up/not-in-catalogue",
                message="x",
                phase=error_codes.PHASE_SCRIPT_EVAL,
            )

    def test_invalid_phase_rejected(self):
        with pytest.raises(ValueError):
            ComposeSandboxViolationError(
                code=error_codes.LAYER_A_EVAL_DENIED,
                message="x",
                phase="made-up-phase",
            )

    def test_script_location_preserved_when_provided(self):
        err = ComposeSandboxViolationError(
            code=error_codes.LAYER_A_EVAL_DENIED,
            message="x",
            phase=error_codes.PHASE_SCRIPT_PARSE,
            script_location=(12, 5),
        )
        assert err.script_location == (12, 5)

    def test_cause_attached_via_ctor(self):
        original = RuntimeError("underlying")
        err = ComposeSandboxViolationError(
            code=error_codes.LAYER_B_INJECTION_SUSPECTED,
            message="suspicious pattern",
            phase=error_codes.PHASE_SCRIPT_PARSE,
            cause=original,
        )
        assert err.__cause__ is original

    def test_all_14_codes_construct_successfully(self):
        """Every catalogue entry must be a valid constructor argument."""
        for code in error_codes.ALL_CODES:
            err = ComposeSandboxViolationError(
                code=code,
                message="x",
                phase=error_codes.PHASE_SCRIPT_PARSE,
            )
            assert err.code == code

    def test_repr_surfaces_diagnostic_fields(self):
        err = ComposeSandboxViolationError(
            code=error_codes.LAYER_C_METHOD_DENIED,
            message="plan.raw() is not on the QueryPlan public surface",
            phase=error_codes.PHASE_SCRIPT_EVAL,
        )
        rep = repr(err)
        assert "ComposeSandboxViolationError" in rep
        assert error_codes.LAYER_C_METHOD_DENIED in rep
        assert "C" in rep  # layer
        assert "method-denied" in rep  # kind
