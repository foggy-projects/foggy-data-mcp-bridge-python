"""Unit tests for calc-field dependency sorter (Kahn's algorithm).

对齐 Java ``CalculatedFieldService.sortByDependencies`` 的行为。

需求：``docs/v1.5/P1-Phase2-计算字段依赖图-需求.md``.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.definitions.query_request import CalculatedFieldDef
from foggy.dataset_model.semantic.calc_field_sorter import (
    CircularCalcFieldError,
    build_dependency_map,
    extract_calc_refs,
    sort_calc_fields_by_dependencies,
)


def _cf(name: str, expr: str) -> CalculatedFieldDef:
    return CalculatedFieldDef(name=name, expression=expr)


# --------------------------------------------------------------------------- #
# extract_calc_refs — dependency discovery
# --------------------------------------------------------------------------- #

class TestExtractCalcRefs:
    def test_no_refs(self):
        assert extract_calc_refs("x + 1", {"a", "b"}) == set()

    def test_one_ref(self):
        assert extract_calc_refs("a * 2", {"a", "b"}) == {"a"}

    def test_multiple_refs(self):
        assert extract_calc_refs("a + b + c", {"a", "b", "c"}) == {"a", "b", "c"}

    def test_only_calc_names_count(self):
        # `salesAmount` is a base column, not a calc name
        assert extract_calc_refs("a + salesAmount", {"a", "b"}) == {"a"}

    def test_strips_string_literals(self):
        # 'a' inside a string literal should NOT count as a ref to calc 'a'
        assert extract_calc_refs("'a' + 'b'", {"a", "b"}) == set()

    def test_mixed_quoted_and_unquoted(self):
        assert extract_calc_refs("a + 'a'", {"a"}) == {"a"}

    def test_empty_expression(self):
        assert extract_calc_refs("", {"a"}) == set()
        assert extract_calc_refs(None, {"a"}) == set()

    def test_sql_keywords_not_counted(self):
        # 'in', 'not', etc. are SQL keywords — filtered by field_validator
        assert extract_calc_refs(
            "status in ('active', 'pending')",
            {"status"},
        ) == {"status"}


# --------------------------------------------------------------------------- #
# sort_calc_fields_by_dependencies — happy paths
# --------------------------------------------------------------------------- #

class TestSortHappy:
    def test_empty(self):
        assert sort_calc_fields_by_dependencies([]) == []

    def test_single(self):
        fields = [_cf("a", "x + 1")]
        result = sort_calc_fields_by_dependencies(fields)
        assert [f.name for f in result] == ["a"]

    def test_no_deps_preserves_input_order(self):
        fields = [_cf("c", "x"), _cf("a", "y"), _cf("b", "z")]
        result = sort_calc_fields_by_dependencies(fields)
        # Stable: c/a/b all have no deps, keep input order
        assert [f.name for f in result] == ["c", "a", "b"]

    def test_simple_chain(self):
        # b depends on a
        fields = [_cf("b", "a * 2"), _cf("a", "x + 1")]
        result = sort_calc_fields_by_dependencies(fields)
        assert [f.name for f in result] == ["a", "b"]

    def test_deep_chain(self):
        # d -> c -> b -> a
        fields = [
            _cf("d", "c + 1"),
            _cf("c", "b * 2"),
            _cf("b", "a - 1"),
            _cf("a", "x"),
        ]
        result = sort_calc_fields_by_dependencies(fields)
        assert [f.name for f in result] == ["a", "b", "c", "d"]

    def test_diamond(self):
        # a → b, a → c, b+c → d
        fields = [
            _cf("d", "b + c"),
            _cf("b", "a + 1"),
            _cf("c", "a - 1"),
            _cf("a", "x"),
        ]
        result = sort_calc_fields_by_dependencies(fields)
        names = [f.name for f in result]
        # a must come first, d must come last
        assert names[0] == "a"
        assert names[-1] == "d"
        # b and c can be in either order relative to each other
        assert set(names[1:3]) == {"b", "c"}
        # Stable: input order was b, c → output should be b, c
        assert names[1:3] == ["b", "c"]

    def test_multiple_independent_chains(self):
        # Chain 1: a → b
        # Chain 2: c → d
        # No cross-deps
        fields = [
            _cf("b", "a + 1"),
            _cf("d", "c + 1"),
            _cf("a", "x"),
            _cf("c", "y"),
        ]
        result = sort_calc_fields_by_dependencies(fields)
        names = [f.name for f in result]
        # a must precede b; c must precede d
        assert names.index("a") < names.index("b")
        assert names.index("c") < names.index("d")

    def test_self_reference_not_cycle(self):
        # `a` references itself syntactically — Java silently ignores; do the same
        fields = [_cf("a", "a + 1")]
        result = sort_calc_fields_by_dependencies(fields)
        assert [f.name for f in result] == ["a"]

    def test_base_columns_not_counted_as_calc(self):
        # `price`, `discount` are base columns, not calc fields.
        # calc 'a' depends on nothing (calc-wise).
        fields = [_cf("a", "price - discount")]
        result = sort_calc_fields_by_dependencies(fields)
        assert [f.name for f in result] == ["a"]


# --------------------------------------------------------------------------- #
# sort_calc_fields_by_dependencies — cycle detection
# --------------------------------------------------------------------------- #

class TestSortCycle:
    def test_two_cycle(self):
        fields = [_cf("a", "b + 1"), _cf("b", "a - 1")]
        with pytest.raises(CircularCalcFieldError) as ei:
            sort_calc_fields_by_dependencies(fields)
        assert set(ei.value.fields) == {"a", "b"}

    def test_three_cycle(self):
        fields = [
            _cf("a", "b + 1"),
            _cf("b", "c + 1"),
            _cf("c", "a + 1"),
        ]
        with pytest.raises(CircularCalcFieldError) as ei:
            sort_calc_fields_by_dependencies(fields)
        assert set(ei.value.fields) == {"a", "b", "c"}

    def test_cycle_error_message_contains_all_participants(self):
        fields = [_cf("x", "y + 1"), _cf("y", "x - 1")]
        with pytest.raises(CircularCalcFieldError, match=r"\['x', 'y'\]"):
            sort_calc_fields_by_dependencies(fields)

    def test_cycle_error_is_valueerror(self):
        """CircularCalcFieldError is a subclass of ValueError for
        backward-compatible except-handling in callers."""
        fields = [_cf("a", "b"), _cf("b", "a")]
        with pytest.raises(ValueError):
            sort_calc_fields_by_dependencies(fields)

    def test_mixed_cycle_and_good_fields(self):
        # Good: g depends on nothing
        # Cycle: a ↔ b
        fields = [
            _cf("g", "x + 1"),
            _cf("a", "b + 1"),
            _cf("b", "a - 1"),
        ]
        with pytest.raises(CircularCalcFieldError) as ei:
            sort_calc_fields_by_dependencies(fields)
        assert set(ei.value.fields) == {"a", "b"}  # g is NOT in cycle

    def test_cycle_blocks_dependent_too(self):
        # a ↔ b cycle; c depends on a → c also unresolvable
        fields = [
            _cf("c", "a + 1"),
            _cf("a", "b + 1"),
            _cf("b", "a - 1"),
        ]
        with pytest.raises(CircularCalcFieldError) as ei:
            sort_calc_fields_by_dependencies(fields)
        assert set(ei.value.fields) == {"a", "b", "c"}


# --------------------------------------------------------------------------- #
# Stability / input-order invariants
# --------------------------------------------------------------------------- #

class TestStability:
    def test_zero_degree_fields_keep_input_order(self):
        """When multiple fields have zero dependency, Kahn's fifo queue
        in input order → output keeps input order."""
        fields = [_cf("z", "x"), _cf("a", "y"), _cf("m", "n")]
        result = sort_calc_fields_by_dependencies(fields)
        assert [f.name for f in result] == ["z", "a", "m"]

    def test_dependents_keep_input_order_when_ready(self):
        # a has no deps; b depends on a; c depends on a.
        # After a, queue adds b then c (input order).
        fields = [
            _cf("a", "x"),
            _cf("c", "a + 1"),
            _cf("b", "a - 1"),
        ]
        result = sort_calc_fields_by_dependencies(fields)
        names = [f.name for f in result]
        assert names[0] == "a"
        # c was added to queue before b because input order is c, b
        assert names[1] == "c"
        assert names[2] == "b"


# --------------------------------------------------------------------------- #
# build_dependency_map — tooling/debug helper
# --------------------------------------------------------------------------- #

class TestBuildDepMap:
    def test_basic(self):
        fields = [_cf("a", "x"), _cf("b", "a + 1"), _cf("c", "a + b")]
        dmap = build_dependency_map(fields)
        assert dmap == {"a": set(), "b": {"a"}, "c": {"a", "b"}}

    def test_ignores_base_columns(self):
        fields = [_cf("a", "price - discount")]
        assert build_dependency_map(fields) == {"a": set()}

    def test_ignores_self_ref(self):
        fields = [_cf("a", "a + 1")]
        assert build_dependency_map(fields) == {"a": set()}
