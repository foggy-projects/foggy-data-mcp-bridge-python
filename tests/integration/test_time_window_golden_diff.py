"""TimeWindow Java snapshot parity checks (Stage 3).

Exercises the Java timeWindow parity catalog and asserts Python SQL output
matches the Java fixture's structural expectations.

The structural assertions verify:

- Python produces valid SQL (no error)
- Expected columns from the Java fixture are present in the Python output
- SQL contains the expected structural markers (post-calc FROM wrapper,
  comparative CTE, window frame, etc.)

When ``_time_window_parity_snapshot.json`` is present, the snapshot test
validates Java-side schema, success/error coverage, and semantic SQL markers,
then cross-checks that Python produces valid SQL for the same Java-success
cases. Full token-by-token normalized SQL diff is intentionally deferred until
the normalizer can canonicalize multi-CTE query structures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest

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

_EXPECTED_JAVA_GENERATION_ERRORS: dict[str, str] = {}


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
    request_columns = case.get("requestColumns")

    if comparison.startswith("rolling_"):
        columns = request_columns or ["salesDate$id", "salesAmount", *expected_columns]
        return _unique(list(columns)), ["salesDate$id"]

    if comparison == "yoy":
        group_by = ["salesDate$year", "salesDate$month"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    if comparison == "mom":
        group_by = ["salesDate$month", "salesDate$id"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    if comparison == "mtd":
        group_by = ["salesDate$year", "salesDate$month", "salesDate$id"]
        columns = request_columns or [*group_by, "salesAmount", *expected_columns]
        return _unique(list(columns)), group_by

    if comparison == "ytd":
        group_by = ["salesDate$year", "salesDate$id"]
        columns = request_columns or [*group_by, "salesAmount", *expected_columns]
        return _unique(list(columns)), group_by

    if comparison == "wow":
        group_by = ["salesDate$week", "salesDate$dayOfWeek"]
        columns = request_columns or expected_columns
        return _unique(list(columns)), group_by

    columns = request_columns or ["salesDate$id", "salesAmount", *expected_columns]
    return _unique(list(columns)), ["salesDate$id"]


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
    """Stage 3: structural key-marker diff for Java timeWindow snapshots.

    Both Java and Python compile paths produce semantically equivalent but
    syntactically different SQL (different CTE naming, subquery structure,
    bind-param strategy).  Full token-by-token normalized SQL diff would
    require the normalizer to be extended for multi-CTE query structures
    (Stage 4+ scope).

    This test validates that the Java snapshot contains the expected current
    success set with no Java-side generation drift. Successful Java snapshots
    are then checked for semantic SQL markers and replayed through the Python
    validate path.

    When the normalizer is extended for full-query normalization, this
    test can be upgraded to use ``assert_golden_cases`` directly.
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

    # Schema validation
    assert snapshot.get("schema_version") == "1"
    assert snapshot.get("source") == "TimeWindowParitySnapshotTest"
    assert snapshot.get("feature") == "timeWindow"

    java_by_name: dict[str, dict] = {
        row["name"]: row for row in snapshot.get("snapshots", [])
    }
    java_errors_by_name: dict[str, dict] = {
        row["name"]: row for row in snapshot.get("generation_errors", [])
    }

    catalog = _load_catalog()
    happy_cases = [entry for entry in catalog if "expectedError" not in entry]
    happy_names = {entry["name"] for entry in happy_cases}

    assert set(java_errors_by_name) == set(_EXPECTED_JAVA_GENERATION_ERRORS)
    for name, marker in _EXPECTED_JAVA_GENERATION_ERRORS.items():
        error = java_errors_by_name[name]
        assert error["error_code"] == "GENERATE_SQL_FAILED"
        assert marker in error["message"]

    assert set(java_by_name) == happy_names - set(_EXPECTED_JAVA_GENERATION_ERRORS)
    assert len(java_by_name) == 9

    for entry in happy_cases:
        if entry["name"] in java_errors_by_name:
            continue
        java_sql = java_by_name[entry["name"]]["sql_normalized"]
        _assert_java_sql_markers(entry, java_sql)

        py_sql, py_cols = _run_python_query(entry)
        assert py_sql, f"Python SQL is empty for {entry['name']}"
        assert java_sql, f"Java SQL is empty for {entry['name']}"
        assert len(py_sql) > 50, f"Python SQL suspiciously short for {entry['name']}"
        assert len(java_sql) > 50, f"Java SQL suspiciously short for {entry['name']}"
        assert set(entry["expectedColumns"]).issubset(set(py_cols))


def _assert_java_sql_markers(case: dict[str, Any], sql: str) -> None:
    assert sql, f"Java SQL is empty for {case['name']}"
    for column in case.get("expectedColumns", []):
        assert f'"{column}"' in sql, (
            f"Java SQL for {case['name']} missing expected column {column}"
        )

    assertions = case.get("assertions", {})
    if "windowFrame" in assertions:
        assert assertions["windowFrame"] in sql

    comparison = case["comparison"]
    if comparison in {"yoy", "mom"}:
        assert '"salesAmount__prior"' in sql
        assert '"salesAmount__diff"' in sql
        assert '"salesAmount__ratio"' in sql
        assert "LEFT JOIN" in sql
    if comparison in {"rolling_7d", "rolling_30d", "mtd", "ytd"}:
        assert "OVER" in sql
    if comparison in {"mtd", "ytd"}:
        assert "UNBOUNDED PRECEDING" in sql
    if assertions.get("postCalcFieldPresent"):
        for calc in case.get("calculatedFields", []):
            assert f'AS "{calc["name"]}"' in sql
