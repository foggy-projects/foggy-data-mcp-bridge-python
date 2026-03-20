"""Tests for calculated fields (DbFormulaDef) — aligned with Java CalculatedFieldTest
and CalculatedFieldAggregationBugTest."""

import pytest

from foggy.dataset_model.definitions.measure import DbFormulaDef, FormulaOperator


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_formula(expression: str, **kwargs) -> DbFormulaDef:
    """Create a DbFormulaDef with sensible defaults."""
    return DbFormulaDef(name=kwargs.pop("name", "test_formula"), expression=expression, **kwargs)


# ===========================================================================
# TestDbFormulaDef — evaluate() tests
# ===========================================================================

class TestDbFormulaDef:
    """Tests for DbFormulaDef.evaluate() using safe AST-based evaluation."""

    # -- basic arithmetic ---------------------------------------------------

    def test_simple_arithmetic(self):
        formula = _make_formula("salesAmount - discountAmount")
        result = formula.evaluate({"salesAmount": 100, "discountAmount": 20})
        assert result == 80.0

    def test_multiplication(self):
        formula = _make_formula("unitPrice * quantity")
        result = formula.evaluate({"unitPrice": 10.5, "quantity": 3})
        assert result == pytest.approx(31.5)

    def test_division(self):
        formula = _make_formula("profitAmount / salesAmount * 100")
        result = formula.evaluate({"profitAmount": 30, "salesAmount": 100})
        assert result == pytest.approx(30.0)

    def test_division_by_zero(self):
        """Division by zero should return None (exception handled)."""
        formula = _make_formula("a / b")
        result = formula.evaluate({"a": 10, "b": 0})
        assert result is None

    def test_complex_expression(self):
        formula = _make_formula("(salesAmount - discountAmount) * 0.9")
        result = formula.evaluate({"salesAmount": 100, "discountAmount": 20})
        assert result == pytest.approx(72.0)

    def test_nested_parentheses(self):
        formula = _make_formula("((a + b) * (c - d)) / e")
        result = formula.evaluate({"a": 2, "b": 3, "c": 10, "d": 4, "e": 5})
        # ((2+3) * (10-4)) / 5 = (5 * 6) / 5 = 6.0
        assert result == pytest.approx(6.0)

    def test_unary_minus(self):
        formula = _make_formula("-a + b")
        result = formula.evaluate({"a": 3, "b": 10})
        assert result == pytest.approx(7.0)

    def test_power(self):
        formula = _make_formula("a ** 2")
        result = formula.evaluate({"a": 5})
        assert result == pytest.approx(25.0)

    def test_floor_div(self):
        formula = _make_formula("a // b")
        result = formula.evaluate({"a": 7, "b": 2})
        assert result == pytest.approx(3.0)

    def test_modulo(self):
        formula = _make_formula("a % b")
        result = formula.evaluate({"a": 7, "b": 3})
        assert result == pytest.approx(1.0)

    # -- edge cases ---------------------------------------------------------

    def test_unknown_variable(self):
        """Unknown variable should cause evaluate() to return None."""
        formula = _make_formula("unknown + 1")
        result = formula.evaluate({"a": 10})
        assert result is None

    def test_unsafe_expression_blocked(self):
        """Unsafe code-injection expression must NOT execute; returns None."""
        formula = _make_formula("__import__('os').system('rm -rf /')")
        result = formula.evaluate({})
        assert result is None

    def test_non_numeric_ignored(self):
        """String values in the dict should be filtered out (only numerics kept)."""
        formula = _make_formula("a + b")
        result = formula.evaluate({"a": 10, "b": "not_a_number"})
        # 'b' is filtered out → unknown variable → None
        assert result is None

    def test_numeric_with_string_mix(self):
        """When the expression only uses numeric keys, strings are silently ignored."""
        formula = _make_formula("a + 1")
        result = formula.evaluate({"a": 5, "extra": "hello"})
        assert result == pytest.approx(6.0)

    def test_empty_values(self):
        """Empty values dict with variable references → None."""
        formula = _make_formula("x + y")
        result = formula.evaluate({})
        assert result is None

    def test_constant_expression(self):
        """Expression with no variables should work."""
        formula = _make_formula("2 + 3 * 4")
        result = formula.evaluate({})
        assert result == pytest.approx(14.0)

    def test_float_precision(self):
        formula = _make_formula("a / b")
        result = formula.evaluate({"a": 1, "b": 3})
        assert result == pytest.approx(0.333333, rel=1e-4)

    def test_large_numbers(self):
        formula = _make_formula("a * b")
        result = formula.evaluate({"a": 1_000_000, "b": 1_000_000})
        assert result == pytest.approx(1e12)


# ===========================================================================
# TestCalculatedFieldValidation — validate_definition() tests
# ===========================================================================

class TestCalculatedFieldValidation:
    """Tests for DbFormulaDef.validate_definition() — unsafe keyword detection."""

    def test_valid_formula(self):
        formula = _make_formula("a + b")
        errors = formula.validate_definition()
        assert errors == []

    def test_unsafe_keyword_import(self):
        formula = _make_formula("import os")
        errors = formula.validate_definition()
        assert any("import" in e for e in errors)

    def test_unsafe_keyword_exec(self):
        formula = _make_formula("exec('print(1)')")
        errors = formula.validate_definition()
        assert any("exec" in e for e in errors)

    def test_unsafe_keyword_eval(self):
        formula = _make_formula("eval('1+1')")
        errors = formula.validate_definition()
        assert any("eval" in e for e in errors)

    def test_unsafe_keyword_dunder(self):
        formula = _make_formula("__import__('os')")
        errors = formula.validate_definition()
        assert any("__" in e for e in errors)

    def test_unsafe_keyword_open(self):
        formula = _make_formula("open('/etc/passwd')")
        errors = formula.validate_definition()
        assert any("open" in e for e in errors)

    def test_empty_expression_error(self):
        formula = DbFormulaDef(name="empty", expression="")
        errors = formula.validate_definition()
        assert any("expression" in e for e in errors)

    def test_complex_safe_expression(self):
        """A complex but safe expression should produce no errors."""
        formula = _make_formula("((salesAmount - discountAmount) * 0.9) / totalCount")
        errors = formula.validate_definition()
        assert errors == []


# ===========================================================================
# TestFormulaOperator enum
# ===========================================================================

class TestFormulaOperator:
    def test_operator_values(self):
        assert FormulaOperator.ADD.value == "+"
        assert FormulaOperator.SUBTRACT.value == "-"
        assert FormulaOperator.MULTIPLY.value == "*"
        assert FormulaOperator.DIVIDE.value == "/"
        assert FormulaOperator.MODULO.value == "%"
