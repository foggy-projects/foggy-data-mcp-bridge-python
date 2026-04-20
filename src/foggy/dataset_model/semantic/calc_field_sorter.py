"""Calculated-field dependency sorting and cycle detection.

对齐 Java ``CalculatedFieldService.sortByDependencies`` (lines 143-205) —
基于 Kahn 算法对计算字段做拓扑排序，让 calc B 引用 calc A 时 A 先编译。

循环引用抛 ``ValueError``，错误消息含**所有**参与循环的字段名。

Python 侧需求：``docs/v1.5/P1-Phase2-计算字段依赖图-需求.md``。
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional, Set

from foggy.dataset_model.definitions.query_request import CalculatedFieldDef
from foggy.dataset_model.semantic.field_validator import _extract_field_dependencies


__all__ = [
    "sort_calc_fields_by_dependencies",
    "extract_calc_refs",
    "CircularCalcFieldError",
]


class CircularCalcFieldError(ValueError):
    """Raised when a cycle is detected in calculated-field dependencies.

    Inherits from ``ValueError`` for backward compatibility with callers
    that catch ``ValueError``.  The ``fields`` attribute exposes the
    exact cycle participants for programmatic handling.
    """

    def __init__(self, fields: Iterable[str]):
        self.fields: List[str] = sorted(fields)
        super().__init__(
            f"Circular reference detected in calculated fields: "
            f"{self.fields}. "
            f"Check these expressions - each references another in the cycle."
        )


def extract_calc_refs(expression: str, calc_names: Set[str]) -> Set[str]:
    """Extract calc-to-calc references from an expression.

    Uses ``field_validator._extract_field_dependencies`` (regex-based,
    string-literal aware, SQL-keyword-filtered) and then intersects with
    the set of known calc field names.  Any reference outside
    ``calc_names`` is treated as a base column / dimension / measure and
    left for the normal field resolver.
    """
    if not expression:
        return set()
    deps = _extract_field_dependencies(expression)
    return deps & calc_names


def sort_calc_fields_by_dependencies(
    calc_fields: List[CalculatedFieldDef],
) -> List[CalculatedFieldDef]:
    """Topologically sort ``calc_fields`` so that each field appears after
    every calc field it depends on.

    Uses Kahn's algorithm with a FIFO queue seeded in **input order** —
    so two fields with no mutual dependencies retain their original
    relative position, giving callers stable, predictable SQL output.

    Self-references (``a`` inside ``a``'s own expression) are treated as
    *not-a-cycle* and silently ignored, matching Java behaviour.  A true
    cycle (``a → b → a`` or longer) raises :class:`CircularCalcFieldError`.

    Args:
        calc_fields: calc field definitions, any order.

    Returns:
        A new list in dependency-respecting order.  Original objects
        (not copies) are re-ordered; the input list is not mutated.

    Raises:
        CircularCalcFieldError: if a cycle exists. The error includes the
            full set of fields that could not be sorted (i.e. the cycle's
            participants and any fields transitively blocked on the cycle).
    """
    if not calc_fields:
        return []

    # Preserve input order via ordered dict; names must be unique.
    name_to_field: Dict[str, CalculatedFieldDef] = {}
    for cf in calc_fields:
        if cf.name in name_to_field:
            # Duplicate name — pathological input; keep first, drop subsequent
            # to match how upstream validators typically handle it.  Do NOT
            # raise here to keep this sorter single-purpose.
            continue
        name_to_field[cf.name] = cf

    all_names: Set[str] = set(name_to_field.keys())
    input_order: List[str] = list(name_to_field.keys())

    # deps[name] = set of calc field names that `name` depends on
    deps: Dict[str, Set[str]] = {}
    # reverse[name] = set of calc field names that depend on `name`
    reverse: Dict[str, Set[str]] = {name: set() for name in all_names}

    for name in input_order:
        cf = name_to_field[name]
        refs = extract_calc_refs(cf.expression or "", all_names)
        # Self-reference is not a cycle per Java contract; silently drop.
        refs.discard(name)
        deps[name] = refs
        for r in refs:
            reverse[r].add(name)

    # Kahn's algorithm
    in_degree: Dict[str, int] = {name: len(deps[name]) for name in all_names}
    queue: deque[str] = deque(name for name in input_order if in_degree[name] == 0)
    sorted_names: List[str] = []

    while queue:
        current = queue.popleft()
        sorted_names.append(current)
        # Process dependents in stable (input) order
        dependents_in_input_order = [n for n in input_order if n in reverse[current]]
        for dependent in dependents_in_input_order:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(sorted_names) < len(input_order):
        # Whatever didn't land in `sorted_names` is either in the cycle
        # or transitively blocked by it.  Java reports all such fields;
        # we mirror that to help the user locate every broken link.
        unsorted = all_names - set(sorted_names)
        raise CircularCalcFieldError(unsorted)

    return [name_to_field[n] for n in sorted_names]


# For callers that want just the dependency map (e.g. debugging tools)
def build_dependency_map(
    calc_fields: List[CalculatedFieldDef],
) -> Dict[str, Set[str]]:
    """Return a map from each calc field name to the set of calc field
    names it references in its expression.  Does NOT perform sorting or
    cycle detection.  Useful for debugging / tooling.
    """
    all_names = {cf.name for cf in calc_fields}
    out: Dict[str, Set[str]] = {}
    for cf in calc_fields:
        refs = extract_calc_refs(cf.expression or "", all_names)
        refs.discard(cf.name)
        out[cf.name] = refs
    return out
