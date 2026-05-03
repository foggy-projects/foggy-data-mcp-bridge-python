"""Executable parity checks for docs/v1.5.1 restricted CALCULATE catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.formula_compiler import (
    CalculateQueryContext,
    FormulaCompiler,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from foggy.dataset_model.semantic.formula_errors import FormulaSyntaxError


CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "v1.5.1"
    / "P1-CALCULATE-restricted-mvp-parity-catalog.json"
)


def _resolver(name: str) -> str:
    return {
        "salesAmount": "t.sales_amount",
        "customer$customerType": "dc.customer_type",
        "product$categoryName": "dp.category_name",
    }.get(name, name)


def _load_cases() -> list[dict[str, Any]]:
    with CATALOG_PATH.open("r", encoding="utf-8") as fp:
        catalog = json.load(fp)
    return catalog["cases"]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["id"])
def test_calculate_mvp_parity_catalog(case: dict[str, Any]) -> None:
    compiler = FormulaCompiler(SqlDialect.of(case.get("dialect") or "sqlite"))
    ctx = CalculateQueryContext(
        group_by_fields=tuple(case.get("groupBy") or ()),
        system_slice_fields=frozenset(case.get("systemSliceFields") or ()),
        supports_grouped_aggregate_window=case.get("id") != "calculate_mysql_57_window_unsupported",
        time_window_post_calculated_fields=bool(case.get("timeWindowPostCalculatedFields")),
    )

    expected_error = case.get("expectError")
    if expected_error:
        with pytest.raises(FormulaSyntaxError, match=expected_error):
            compiler.compile(case["expression"], _resolver, calculate_context=ctx)
        return

    result = compiler.compile(case["expression"], _resolver, calculate_context=ctx)
    for fragment in case.get("expectSqlContains") or ():
        assert fragment in result.sql_fragment
