"""Extract referenced QM field names from formula expressions.

Used for fail-closed permission enforcement: if any field referenced
by a formula is denied, the formula itself must be hidden/rejected.

Strategy: tokenize the expression and extract bare identifiers that
are not SQL keywords, function names, or literal values.

Examples::

    >>> extract_formula_fields("sum(if(move$moveType == 'out_invoice', amountResidual, 0))")
    {'move$moveType', 'amountResidual'}

    >>> extract_formula_fields("count(distinct(if(... dateMaturity < now(), partner$id, null)))")
    {'move$moveType', 'move$state', 'move$paymentState', 'dateMaturity', 'partner$id'}
"""

import re
from typing import Set, Dict, Optional

# SQL/formula reserved words that should NOT be treated as field references.
# Includes common SQL keywords, formula functions, and boolean/null literals.
_RESERVED_WORDS: Set[str] = {
    # SQL keywords
    "and", "or", "not", "in", "is", "null", "true", "false",
    "between", "like", "case", "when", "then", "else", "end",
    "as", "asc", "desc", "select", "from", "where", "group",
    "by", "having", "order", "limit", "offset", "union", "all",
    "exists", "any", "some",
    # Formula functions (commonly used in QM formulas)
    "sum", "avg", "count", "min", "max",
    "if", "coalesce", "nullif", "ifnull",
    "abs", "round", "ceil", "floor", "mod", "power", "sqrt",
    "year", "month", "day", "date", "now", "today", "datetime",
    "date_add", "date_sub", "date_diff", "datediff",
    "concat", "substring", "upper", "lower", "trim", "length",
    "distinct", "cast",
    # CALCULATE formula keywords
    "calculate", "remove",
}

# Regex: match identifiers that may contain $ (for dim$field references).
# An identifier starts with a letter or underscore and may contain
# letters, digits, underscores, and the $ separator.
_IDENTIFIER_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_$]*)\b")


def extract_formula_fields(expression: str) -> Set[str]:
    """Extract QM field names referenced in a formula expression.

    Args:
        expression: Formula expression string (e.g.,
            ``"sum(if(move$moveType == 'out_invoice', amountResidual, 0))"``)

    Returns:
        Set of QM field names (e.g., ``{'move$moveType', 'amountResidual'}``)
    """
    if not expression:
        return set()

    # Step 1: Remove string literals (single-quoted and double-quoted)
    # so their content isn't parsed as identifiers.
    cleaned = re.sub(r"'[^']*'", "", expression)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)

    # Step 2: Extract all identifier-like tokens
    tokens = _IDENTIFIER_RE.findall(cleaned)

    # Step 3: Filter out reserved words and pure numeric tokens
    fields: Set[str] = set()
    for token in tokens:
        if token.lower() in _RESERVED_WORDS:
            continue
        # Skip tokens that are entirely numeric (shouldn't match regex, but safety)
        if token.isdigit():
            continue
        fields.add(token)

    return fields


def resolve_base_column_references(
    expression: str,
    calc_field_map: Dict[str, str],
    seen: Optional[Set[str]] = None,
) -> Set[str]:
    """Recursively resolve all underlying base column references in an expression.

    If a formula references another calculated field (found in calc_field_map),
    it expands that reference. This mirrors the Java CalculatedFieldService's
    recursive resolution for robust governance.

    Args:
        expression: The starting formula expression.
        calc_field_map: Dictionary mapping calculated field names to their expressions.
        seen: Internal set to prevent infinite recursion on circular dependencies.

    Returns:
        Set of base QM field names (excluding calculated field names).
    """
    if seen is None:
        seen = set()

    fields = extract_formula_fields(expression)
    base_fields: Set[str] = set()

    for f in fields:
        if f in calc_field_map and f not in seen:
            seen.add(f)
            # Recursively resolve the referenced formula
            base_fields.update(
                resolve_base_column_references(calc_field_map[f], calc_field_map, seen)
            )
        elif f not in calc_field_map:
            # It's a base field
            base_fields.add(f)

    return base_fields
