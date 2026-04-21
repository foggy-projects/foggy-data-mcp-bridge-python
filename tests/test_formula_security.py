"""Formula compiler security / DoS tests (M5 Step 5.3) — Python side.

Covers the 15+ malicious / abusive inputs listed in
``docs/v1.4/REQ-FORMULA-EXTEND-M5-parity-execution-prompt.md`` §5.3.  Each case
asserts either the specific ``FormulaError`` subclass from
``foggy.dataset_model.semantic.formula_errors`` (and a fragment of the standard
error message template from ``formula-spec-v1/security.md §2.5``), or — for
cases where the grammar makes the attack harmless — that the compiled SQL
quarantines the hostile payload into a bind parameter.

Java owns the mirrored ``FormulaSecurityTest.java``; the two files are kept in
id-locked lockstep so gaps on either side surface immediately.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.semantic.formula_compiler import (
    FormulaCompiler,
    FormulaCompilerConfig,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from foggy.dataset_model.semantic.formula_errors import (
    FormulaAggNotOutermostError,
    FormulaDepthError,
    FormulaError,
    FormulaFunctionNotAllowedError,
    FormulaInListSizeError,
    FormulaNodeNotAllowedError,
    FormulaNullComparisonError,
    FormulaSecurityError,
    FormulaSyntaxError,
)


def _resolver(name: str) -> str:  # passthrough
    return name


@pytest.fixture
def compiler() -> FormulaCompiler:
    return FormulaCompiler(SqlDialect.of("mysql"))


# --------------------------------------------------------------------------- #
# sec-01 ~ sec-02 · SQL injection payloads — neutralized as bind params
# --------------------------------------------------------------------------- #


class TestInjectionNeutralization:
    """Payloads that Spec v1 deliberately **quarantines** (bind param)
    instead of rejecting at parse time.  Proof-of-safety: the rendered SQL
    string must not contain the payload verbatim."""

    def test_sec_01_drop_table_string_literal(
        self, compiler: FormulaCompiler
    ) -> None:
        payload = "1); DROP TABLE users; --"
        r = compiler.compile(f"'{payload}'", _resolver)
        assert r.sql_fragment == "?"
        assert r.bind_params == (payload,)
        assert "DROP" not in r.sql_fragment
        assert ";" not in r.sql_fragment

    def test_sec_02_injection_in_if_branch(
        self, compiler: FormulaCompiler
    ) -> None:
        r = compiler.compile(
            "if(status == 'active; DROP TABLE x', 1, 0)", _resolver
        )
        # The payload ends up in bind_params, not in the SQL string.
        assert "DROP" not in r.sql_fragment
        assert ";" not in r.sql_fragment
        assert "active; DROP TABLE x" in r.bind_params


# --------------------------------------------------------------------------- #
# sec-03 ~ sec-07 · Sandbox escapes rejected by validator
# --------------------------------------------------------------------------- #


class TestSandboxEscapeRejected:
    def test_sec_03_dunder_identifier(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaSecurityError) as exc:
            compiler.compile("__class__", _resolver)
        assert "__" in str(exc.value)

    def test_sec_04_member_access(self, compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaNodeNotAllowedError) as exc:
            compiler.compile("x.attr", _resolver)
        assert "MemberAccessExpression" in str(exc.value) or (
            "not allowed" in str(exc.value)
        )

    def test_sec_05_getattr_function_rejected(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaFunctionNotAllowedError) as exc:
            compiler.compile("getattr(x, 'password')", _resolver)
        assert "getattr" in str(exc.value)

    def test_sec_06_eval_function_rejected(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaFunctionNotAllowedError):
            compiler.compile("eval(1)", _resolver)

    def test_sec_07_exec_function_rejected(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaFunctionNotAllowedError):
            compiler.compile("exec('import os')", _resolver)


# --------------------------------------------------------------------------- #
# sec-08 ~ sec-10 · DoS / hard caps
# --------------------------------------------------------------------------- #


class TestDoSHardCaps:
    def test_sec_08_depth_exceeded(self) -> None:
        """40-level ``if`` nesting must trip the depth hard cap (default 32)."""
        compiler = FormulaCompiler(SqlDialect.of("mysql"))
        expr = "1"
        for _ in range(40):
            expr = f"if(true, {expr}, 0)"
        with pytest.raises(FormulaDepthError) as exc:
            compiler.compile(expr, _resolver)
        assert "depth" in str(exc.value).lower()

    def test_sec_09_in_list_size_exceeded(self) -> None:
        """1025-member IN list trips the 1024 hard cap (Spec §3.2 / security.md §3)."""
        # Default max_expr_len is 4096 — raise it so we exercise the IN cap
        # rather than the length cap.
        compiler = FormulaCompiler(
            SqlDialect.of("mysql"),
            config=FormulaCompilerConfig(max_expr_len=100_000),
        )
        members = ", ".join(str(i) for i in range(1025))
        with pytest.raises(FormulaInListSizeError) as exc:
            compiler.compile(f"id in ({members})", _resolver)
        assert "IN list size" in str(exc.value)

    def test_sec_10_expression_length_exceeded(
        self, compiler: FormulaCompiler
    ) -> None:
        """Expressions > max_expr_len must trip ``FormulaSecurityError`` before parse."""
        expr = "a" + " + a" * 2000  # ~8001 chars, well over default 4096
        with pytest.raises(FormulaSecurityError) as exc:
            compiler.compile(expr, _resolver)
        assert "length" in str(exc.value).lower() or (
            "exceeds" in str(exc.value).lower()
        )


# --------------------------------------------------------------------------- #
# sec-11 ~ sec-17 · Grammar / semantic rejects
# --------------------------------------------------------------------------- #


class TestGrammarRejects:
    def test_sec_11_null_comparison(self, compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaNullComparisonError) as exc:
            compiler.compile("x == null", _resolver)
        assert "is_null" in str(exc.value) or (
            "Null comparison" in str(exc.value)
        )

    def test_sec_12_power_operator_rejected(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaSyntaxError):
            compiler.compile("a ** 2", _resolver)

    def test_sec_13_distinct_outside_count(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(
            (FormulaAggNotOutermostError, FormulaFunctionNotAllowedError)
        ) as exc:
            compiler.compile("count(distinct(x) + 1)", _resolver)
        assert "distinct" in str(exc.value).lower()

    def test_sec_14_agg_not_outermost(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaAggNotOutermostError) as exc:
            compiler.compile("sum(x) + 1", _resolver)
        assert "sum" in str(exc.value).lower()

    def test_sec_15_unknown_function_rejected(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaFunctionNotAllowedError) as exc:
            compiler.compile("median(a)", _resolver)
        assert "median" in str(exc.value)

    def test_sec_16_wrong_arg_count(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaSyntaxError) as exc:
            compiler.compile("if(cond, x, y, z)", _resolver)
        assert "argument" in str(exc.value).lower()

    def test_sec_17_date_add_invalid_unit(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaSyntaxError) as exc:
            compiler.compile("date_add(today, 30, 'hour')", _resolver)
        assert "unit" in str(exc.value).lower()


# --------------------------------------------------------------------------- #
# sec-18+ · Additional hardening
# --------------------------------------------------------------------------- #


class TestAdditionalHardening:
    def test_sec_18_round_n_out_of_range(
        self, compiler: FormulaCompiler
    ) -> None:
        with pytest.raises(FormulaSyntaxError) as exc:
            compiler.compile("round(x, 15)", _resolver)
        assert "round" in str(exc.value).lower()

    def test_sec_19_dunder_import(self, compiler: FormulaCompiler) -> None:
        """``__import__('os')`` — the dunder identifier is rejected before
        the non-allowed ``__import__`` is looked up as a function."""
        with pytest.raises((FormulaSecurityError, FormulaFunctionNotAllowedError)):
            compiler.compile("__import__('os')", _resolver)

    def test_sec_20_all_errors_descend_from_formula_error(
        self, compiler: FormulaCompiler
    ) -> None:
        """Sanity: every rejection must be catchable via the ``FormulaError``
        umbrella so upstream consumers can translate to a single HTTP 400."""
        samples = [
            ("__class__", FormulaError),
            ("eval(1)", FormulaError),
            ("x == null", FormulaError),
            ("sum(sum(x))", FormulaError),
        ]
        for expr, base in samples:
            with pytest.raises(base):
                compiler.compile(expr, _resolver)
