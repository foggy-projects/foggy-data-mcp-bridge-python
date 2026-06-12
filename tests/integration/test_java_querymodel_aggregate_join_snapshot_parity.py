"""Replay Java QueryModel aggregate-join neutral snapshots.

This lane is intentionally offline. It validates the Java-exported contract
fixture shape, SQL markers, fail-closed errors, diagnostics, and metadata
lineage while Python production aggregate-join SQL lowering remains disabled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_querymodel_aggregate_join_snapshot_parity.json"
)

REQUIRED_CASE_IDS = {
    "aggregate-join-left-measure-not-multiplied",
    "aggregate-join-sql-shape-sqlite",
    "aggregate-join-missing-right-key-groupby-refusal",
    "aggregate-join-fixed-rhs-filter",
    "aggregate-join-runtime-extdata-filter",
    "aggregate-join-runtime-extdata-missing-refusal",
    "aggregate-join-and-pushdown-diagnostics",
    "aggregate-join-or-outer-only-diagnostics",
    "aggregate-join-denied-source-column-refusal",
    "aggregate-join-field-access-allow-output",
    "aggregate-join-field-access-deny-output-refusal",
    "aggregate-join-system-slice-guard-bypass-no-leak",
    "aggregate-join-denied-source-column-unreferenced-pass",
    "aggregate-join-calculated-field-denied-source-refusal",
    "aggregate-join-calculated-field-chain-denied-source-refusal",
    "aggregate-join-predefined-calculated-field-denied-source-refusal",
    "aggregate-join-predefined-calculated-field-allowed-exec",
    "aggregate-join-raw-sql-access-builder-outer-only",
    "aggregate-join-metadata-lineage",
}

REQUIRED_METADATA_KEYS = {
    "aggregation",
    "sourceCaption",
    "sourceMeasure",
    "sourceAlias",
    "sourceExpression",
    "aggregateExpression",
    "sourceColumn",
}


def _load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_schema_and_required_cases() -> None:
    snapshot = _load_snapshot()

    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "queryModelAggregateJoin"
    assert snapshot["source"] == "JavaQueryModelAggregateJoinSnapshotTest"
    assert snapshot["contractVersion"] == "querymodel-aggregate-join-2"
    assert snapshot["dialect"] == "sqlite"

    case_ids = {case["id"] for case in snapshot["cases"]}
    assert REQUIRED_CASE_IDS == case_ids


def test_java_aggregate_join_snapshot_replays_stable_contract() -> None:
    snapshot = _load_snapshot()

    for case in snapshot["cases"]:
        case_type = case["type"]
        if case_type == "result":
            _assert_result_case(case)
        elif case_type == "sql":
            _assert_sql_case(case)
        elif case_type == "error":
            _assert_error_case(case)
        elif case_type == "metadata":
            _assert_metadata_case(case)
        else:
            raise AssertionError(f"Unsupported aggregate join case type: {case_type!r}")


def test_snapshot_keeps_python_runtime_gap_explicit() -> None:
    snapshot = _load_snapshot()
    case_types = {case["type"] for case in snapshot["cases"]}

    assert {"result", "sql", "error", "metadata"}.issubset(case_types)
    assert _case_by_id(snapshot, "aggregate-join-sql-shape-sqlite")["model"] == (
        "OrderSalesAggregateJoinQueryModel"
    )
    assert _case_by_id(snapshot, "aggregate-join-fixed-rhs-filter")["model"] == (
        "OrderSalesAggregateRelationQueryModel"
    )


def _case_by_id(snapshot: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in snapshot["cases"]:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"Missing aggregate join snapshot case: {case_id}")


def _assert_result_case(case: dict[str, Any]) -> None:
    expected = case["expected"]
    rows = expected["rows"]

    assert rows, f"{case['id']} should include Java result evidence"
    assert expected["leftMeasureNonMultiplicationField"] == "amount"
    assert expected["aggregateOutputFields"] == ["salesAggAmount", "salesLineCount"]

    row = rows[0]
    assert row["amount"] == expected["nativeOrderAmount"]
    assert row["salesAggAmount"] == expected["nativeSalesAmount"]
    assert row["salesLineCount"] == expected["nativeLineCount"]


def _assert_sql_case(case: dict[str, Any]) -> None:
    expected = case["expected"]
    normalized_sql = expected["normalizedSql"]
    normalized_lower = normalized_sql.lower()

    assert " left join " in normalized_lower
    assert "(select" in normalized_lower
    assert " group by " in normalized_lower
    assert isinstance(expected["params"], list)

    for marker in expected.get("sqlMarkers", []):
        assert marker.lower() in normalized_lower, (
            f"{case['id']} missing SQL marker: {marker}"
        )
    for marker in expected.get("forbiddenSqlMarkers", []):
        assert marker.lower() not in normalized_lower, (
            f"{case['id']} contains forbidden SQL marker: {marker}"
        )

    _assert_row_contract(case)
    _assert_diagnostics(expected.get("diagnostics", []))


def _assert_error_case(case: dict[str, Any]) -> None:
    expected = case["expected"]
    error_code = expected["errorCode"]

    assert error_code.startswith("QUERYMODEL_AGGREGATE_JOIN_")
    marker_text = json.dumps(expected, ensure_ascii=False)
    for marker in expected.get("messageMarkers", []):
        assert marker in marker_text, f"{case['id']} missing error marker: {marker}"


def _assert_row_contract(case: dict[str, Any]) -> None:
    expected = case["expected"]
    rows = expected.get("rows", [])

    if rows:
        assert isinstance(rows, list)
        assert all(isinstance(row, dict) for row in rows)

    for field in expected.get("rowsRequiredFields", []):
        assert rows, f"{case['id']} should include row evidence for {field}"
        for row in rows:
            assert field in row, f"{case['id']} row missing required field: {field}"

    for field in expected.get("rowsForbiddenFields", []):
        for row in rows:
            assert field not in row, f"{case['id']} row leaked forbidden field: {field}"

    field_access = expected.get("fieldAccess")
    if field_access is not None:
        assert isinstance(field_access, list)
        allowed = set(field_access)
        for row in rows:
            leaked = set(row) - allowed
            assert not leaked, f"{case['id']} row fields outside fieldAccess: {leaked}"


def _assert_metadata_case(case: dict[str, Any]) -> None:
    expected = case["expected"]
    assert REQUIRED_METADATA_KEYS.issubset(set(expected["aggregateRelation"]))

    fields = expected["fields"]
    for field_name in ("salesAmount", "uniqueCustomers"):
        field = fields[field_name]
        relation = field["aggregateRelation"]
        assert REQUIRED_METADATA_KEYS.issubset(set(relation))
        assert relation["sourceAlias"] == field_name
        assert relation["sourceMeasure"] == field_name
        assert relation["sourceExpression"] == field["sourceExpression"]
        assert relation["aggregateExpression"] == field["aggregateExpression"]


def _assert_diagnostics(diagnostics: list[dict[str, Any]]) -> None:
    for diagnostic in diagnostics:
        assert diagnostic["decision"] in {"pushed", "retained", "refused"}
        assert diagnostic["field"]
        assert diagnostic["op"]
        assert diagnostic["target"] in {"where", "having", "outer"}
        if diagnostic["decision"] == "pushed":
            assert diagnostic["expression"]
        if diagnostic["decision"] == "retained":
            assert diagnostic["reasonCode"]
