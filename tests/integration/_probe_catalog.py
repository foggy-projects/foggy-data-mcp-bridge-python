"""Developer helper: probes Python FormulaCompiler output for each catalog entry.

Not a pytest file — run manually via `python tests/integration/_probe_catalog.py` to
regenerate expected_sql / expected_params values for
`foggy-data-mcp-bridge/foggy-dataset-model/src/test/resources/parity/formula-parity-expressions.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from foggy.dataset_model.semantic.formula_compiler import FormulaCompiler
from foggy.dataset_model.semantic.formula_dialect import SqlDialect

EXPRESSIONS = [
    ("ari-01", "a + b", "mysql"),
    ("ari-02", "(a - b) * 100", "mysql"),
    ("ari-03", "(amountTotal - amountResidual) / amountTotal * 100", "mysql"),
    ("ari-04", "-a", "mysql"),
    ("ari-05", "a % 10", "mysql"),
    ("cmp-01", "a == 10", "mysql"),
    ("cmp-02", "a != 0", "mysql"),
    ("cmp-03", "a >= 100", "mysql"),
    ("cmp-04", "a < b", "mysql"),
    ("bool-01", "(a > 0) && (b < 100)", "mysql"),
    ("bool-02", "(a == 0) || (b > 0)", "mysql"),
    ("bool-03", "!(a == 0)", "mysql"),
    ("in-01", "state in ('posted', 'paid')", "mysql"),
    ("in-02", "companyId in (1, 2, 3)", "mysql"),
    ("in-03", "type not in ('draft')", "mysql"),
    ("if-01", "if(a > 0, a, 0)", "mysql"),
    ("if-02", "if(state == 'posted', 1, 0)", "mysql"),
    ("if-03", "if(a > 0, if(b > 0, 1, 2), 3)", "mysql"),
    ("if-04", "if(overdue, amount, null)", "mysql"),
    ("null-01", "is_null(deletedAt)", "mysql"),
    ("null-02", "is_not_null(confirmedAt)", "mysql"),
    ("null-03", "coalesce(a, 0)", "mysql"),
    ("null-04", "coalesce(a, b, c, 0)", "mysql"),
    ("num-01", "abs(a - b)", "mysql"),
    ("num-02", "round(a / b * 100, 2)", "mysql"),
    ("num-03", "ceil(a / b)", "mysql"),
    ("bt-01", "between(age, 18, 65)", "mysql"),
    ("dt-01-mysql", "date_diff(now(), dateMaturity)", "mysql"),
    ("dt-01-postgres", "date_diff(now(), dateMaturity)", "postgres"),
    ("dt-01-sqlserver", "date_diff(now(), dateMaturity)", "sqlserver"),
    ("dt-01-sqlite", "date_diff(now(), dateMaturity)", "sqlite"),
    ("dt-02-mysql", "date_add(today, 30, 'day')", "mysql"),
    ("dt-02-postgres", "date_add(today, 30, 'day')", "postgres"),
    ("dt-02-sqlserver", "date_add(today, 30, 'day')", "sqlserver"),
    ("dt-03-now-mysql", "now()", "mysql"),
    ("dt-03-now-sqlserver", "now()", "sqlserver"),
    ("agg-01", "sum(if(status == 'cancelled', amount, 0))", "mysql"),
    ("agg-02", "count(distinct(buyerId))", "mysql"),
    ("agg-03", "count(if(amount > 1000, 1, null))", "mysql"),
    ("agg-04", "avg(if(discountAmount > 0, discountAmount, null))", "mysql"),
    ("agg-05", "count(distinct(if(overdue == true, partnerId, null)))", "mysql"),
]


def main() -> None:
    out = []
    for _id, expr, dialect in EXPRESSIONS:
        compiler = FormulaCompiler(SqlDialect.of(dialect))
        try:
            r = compiler.compile(expr, lambda n: n)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {_id}: {expr!r} -> {exc}")
            continue
        out.append({
            "id": _id,
            "expression": expr,
            "dialect": dialect,
            "kind": "positive",
            "expected_sql": r.sql_fragment,
            "expected_params": list(r.bind_params),
        })
    for row in out:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
