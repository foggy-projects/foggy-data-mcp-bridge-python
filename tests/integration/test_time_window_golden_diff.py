"""TimeWindow + calculatedFields post-scalar golden diff (Stage 3).

Exercises the two post-scalar calculatedFields happy cases from the Java
8.5.0 timeWindow parity catalog and asserts Python SQL output matches
the Java fixture's structural expectations.

Full normalized SQL golden diff requires a Java-side snapshot producer
analogous to ``FormulaParitySnapshotTest``; this is documented as a
Stage 3 gap.  The structural assertions here verify:

- Python produces valid SQL (no error)
- Expected columns from the Java fixture are present in the Python output
- SQL contains the expected structural markers (post-calc FROM wrapper,
  comparative CTE, window frame, etc.)

When a Java timeWindow SQL snapshot becomes available, the ``_build_full_sql_cases``
path activates full golden diff through the shared harness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest

from tests.integration._golden_sql_diff import GoldenCase, assert_golden_cases

# --------------------------------------------------------------------------- #
# Fixture loading
# --------------------------------------------------------------------------- #

_CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_time_window_parity_catalog.json"
)

_SNAPSHOT_PATH = Path(__file__).with_name("_time_window_parity_snapshot.json")

# The two post-scalar calculatedFields happy cases targeted by Stage 3.
_POST_SCALAR_CASE_NAMES = {
    "yoy-month-post-calc-growth-happy",
    "rolling_7d-post-calc-gap-happy",
}


def _load_catalog() -> list[dict[str, Any]]:
    if not _CATALOG_PATH.exists():
        pytest.skip(f"timeWindow catalog missing: {_CATALOG_PATH}")
    catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return catalog["cases"]


def _service() -> SemanticQueryService:
    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    return service


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for v in values:
        if v not in result:
            result.append(v)
    return result


def _query_shape(case: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Derive columns and group_by for a catalog case."""
    comparison = case["comparison"]
    expected_columns = list(case.get("expectedColumns", ()))

    if comparison.startswith("rolling_"):
        return _unique(["salesDate$id", "salesAmount", *expected_columns]), ["salesDate$id"]

    if comparison == "yoy":
        group_by = ["salesDate$year", "salesDate$month"]
        return _unique([*expected_columns]), group_by

    if comparison == "mom":
        group_by = ["salesDate$month", "salesDate$id"]
        return _unique([*expected_columns]), group_by

    return _unique(["salesDate$id", "salesAmount", *expected_columns]), ["salesDate$id"]


def _run_python_query(case: dict[str, Any]) -> tuple[str, list[str]]:
    """Run Python SemanticQueryService and return (sql, produced_column_names)."""
    columns, group_by = _query_shape(case)
    response = _service().query_model(
        "FactSalesModel",
        SemanticQueryRequest(
            columns=columns,
            group_by=group_by,
            time_window=case["timeWindow"],
            calculated_fields=case.get("calculatedFields", []),
        ),
        mode="validate",
    )
    assert response.error is None, (
        f"[{case['name']}] Python query failed: {response.error}"
    )
    produced_columns = [col["name"] for col in response.columns]
    return response.sql or "", produced_columns


# --------------------------------------------------------------------------- #
# Structural parity tests (no Java golden SQL required)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "case",
    [c for c in _load_catalog() if c["name"] in _POST_SCALAR_CASE_NAMES],
    ids=lambda c: c["name"],
)
def test_post_scalar_structural_parity(case: dict[str, Any]) -> None:
    """Stage 3: structural parity for post-scalar calculatedFields cases.

    Verifies Python output matches Java fixture expected columns and
    structural assertions without requiring full Java golden SQL.
    """
    sql, produced_columns = _run_python_query(case)

    # 1. Expected columns present
    expected_cols = set(case["expectedColumns"])
    assert expected_cols.issubset(set(produced_columns)), (
        f"[{case['name']}] missing columns: "
        f"{expected_cols - set(produced_columns)}"
    )

    # 2. Structural assertions from Java fixture
    assertions = case.get("assertions", {})

    if assertions.get("postCalcFieldPresent"):
        assert "FROM (\n" in sql, (
            f"[{case['name']}] post-calc wrapper FROM subquery not found in SQL"
        )
        for calc in case.get("calculatedFields", []):
            assert f'AS "{calc["name"]}"' in sql, (
                f"[{case['name']}] calculated field {calc['name']} alias not in SQL"
            )

    if assertions.get("growthPercentEqualsRatioTimes100"):
        assert 'tw_result."salesAmount__ratio"' in sql, (
            f"[{case['name']}] growth percent expression referencing "
            "tw_result.salesAmount__ratio not found"
        )

    if assertions.get("rollingGapEqualsAmountMinusRolling"):
        assert 'tw_result."salesAmount__rolling_7d"' in sql, (
            f"[{case['name']}] rolling gap expression referencing "
            "tw_result.salesAmount__rolling_7d not found"
        )

    # 3. Comparative structure for yoy cases
    if case["comparison"] in {"yoy", "mom", "wow"}:
        assert "WITH __time_window_base AS" in sql
        assert "LEFT JOIN __time_window_base prior ON" in sql


# --------------------------------------------------------------------------- #
# Full golden SQL diff (activated when Java snapshot is available)
# --------------------------------------------------------------------------- #


def test_full_golden_diff_when_snapshot_available() -> None:
    """Stage 3: full golden SQL diff for timeWindow post-scalar cases.

    This test activates when a Java timeWindow SQL snapshot exists at
    ``_time_window_parity_snapshot.json``.  Without the snapshot, it
    skips with a clear message documenting the gap.
    """
    if not _SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java timeWindow SQL snapshot not available. "
            "Full golden SQL diff requires a Java snapshot producer "
            "(TimeWindowParitySnapshotTest). See "
            "docs/v1.5/S3-normalized-sql-golden-diff-progress.md "
            "for the documented gap."
        )

    snapshot = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    java_by_name: dict[str, dict] = {
        row["name"]: row for row in snapshot.get("snapshots", [])
    }

    cases: list[GoldenCase] = []
    catalog = _load_catalog()

    for entry in catalog:
        if entry["name"] not in _POST_SCALAR_CASE_NAMES:
            continue
        java_row = java_by_name.get(entry["name"])
        if java_row is None:
            continue

        sql, _ = _run_python_query(entry)

        cases.append(
            GoldenCase(
                feature="timeWindow",
                case_id=entry["name"],
                dialect="default",
                expected_sql=java_row["sql_normalized"],
                actual_sql=sql,
                expected_params=java_row.get("bind_params"),
                actual_params=None,  # Python SQL has inline literals
                source_hint="_time_window_parity_snapshot.json",
            )
        )

    if not cases:
        pytest.skip("No matching cases found in timeWindow snapshot")

    assert_golden_cases(cases)
