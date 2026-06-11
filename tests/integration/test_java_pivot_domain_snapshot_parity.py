"""Replay Java P0-7 pivot/domain transport neutral snapshots.

The lane intentionally stays offline: Pivot DTO/translation shape and domain
transport renderer contracts are checked without Odoo models or live DBs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.pivot.domain_transport import (
    PIVOT_DOMAIN_TRANSPORT_REFUSED,
    DomainTransportPlan,
    Mysql8DomainRenderer,
    PostgresCteDomainRenderer,
    SqliteCteDomainRenderer,
    assemble_domain_transport_sql,
    build_join_predicate,
    resolve_renderer,
)
from foggy.dataset_model.semantic.pivot.executor import validate_and_translate_pivot
from foggy.mcp_spi import SemanticQueryRequest
from foggy.mcp_spi.semantic import PivotAxisField, PivotMetricItem

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_pivot_domain_snapshot_parity.json"
)

DOMAIN_TRANSPORT_BOUNDARY_CASE_IDS = (
    "domain-sqlite-large-501-transport",
    "domain-sqlite-python-bind-limit-gap",
    "domain-empty-columns-refused",
    "domain-mysql57-derived-table-java-only-gap",
)


def _load_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java pivot/domain snapshot export not available yet: "
            f"{SNAPSHOT_PATH}. P0-7 keeps the replay harness optional until "
            "the Java worktree exports engine-neutral pivot/domain snapshots.",
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "pivotDomainTransport"
    assert snapshot["source"] == "JavaPivotDomainSnapshotTest"
    assert snapshot.get("cases")


def test_java_pivot_domain_snapshot_replays_in_python() -> None:
    snapshot = _load_snapshot()
    for case in snapshot.get("cases", []):
        _assert_case_replays(case)


def test_snapshot_contains_domain_transport_boundary_cases() -> None:
    snapshot = _load_snapshot()
    case_ids = {case["id"] for case in snapshot.get("cases", [])}

    assert set(DOMAIN_TRANSPORT_BOUNDARY_CASE_IDS).issubset(case_ids)


@pytest.mark.parametrize("case_id", DOMAIN_TRANSPORT_BOUNDARY_CASE_IDS)
def test_java_pivot_domain_boundary_case_replays_in_python(case_id: str) -> None:
    snapshot = _load_snapshot()
    case = _case_by_id(snapshot, case_id)

    _assert_case_replays(case)


def test_java_sqlite_two_field_domain_snapshot_executes_live_result() -> None:
    snapshot = _load_snapshot()
    case = _case_by_id(snapshot, "domain-sqlite-two-field-null-safe")
    plan = _plan_from(case["plan"])
    rows = [
        ("A", "p1", 10.0),
        ("A", "p1", 2.0),
        ("A", None, 7.0),
        ("B", "p2", 5.0),
        ("B", None, 100.0),
        ("C", "p3", 99.0),
    ]

    result = _execute_sqlite_domain_transport(
        plan=plan,
        seed_rows=rows,
        select_sql=(
            'SELECT f."category", f."product", SUM(f."amount") AS "metric"\n'
            'FROM "fact_sales" AS f\n'
            'GROUP BY f."category", f."product"'
        ),
        field_sql_map={
            "category": 'f."category"',
            "product": 'f."product"',
        },
    )
    oracle = _execute_sqlite_oracle(
        seed_rows=rows,
        sql=(
            'SELECT f."category", f."product", SUM(f."amount") AS "metric"\n'
            'FROM "fact_sales" AS f\n'
            "WHERE (f.\"category\" = ? AND f.\"product\" = ?)\n"
            "   OR (f.\"category\" = ? AND f.\"product\" IS NULL)\n"
            "   OR (f.\"category\" = ? AND f.\"product\" = ?)\n"
            'GROUP BY f."category", f."product"'
        ),
        params=["A", "p1", "A", "B", "p2"],
    )

    assert _normalize_sqlite_rows(result) == _normalize_sqlite_rows(oracle)
    assert _normalize_sqlite_rows(result) == [
        {"category": "A", "product": "p1", "metric": 12.0},
        {"category": "A", "product": None, "metric": 7.0},
        {"category": "B", "product": "p2", "metric": 5.0},
    ]


def test_java_sqlite_large_501_domain_snapshot_executes_live_result() -> None:
    snapshot = _load_snapshot()
    case = _case_by_id(snapshot, "domain-sqlite-large-501-transport")
    plan = _plan_from(case["plan"])
    rows = [
        ("Category-0", None, 1.0),
        ("Category-42", None, 2.0),
        ("Category-42", None, 3.0),
        ("Category-500", None, 4.0),
        ("Category-outside", None, 99.0),
    ]

    result = _execute_sqlite_domain_transport(
        plan=plan,
        seed_rows=rows,
        select_sql=(
            'SELECT f."category", SUM(f."amount") AS "metric"\n'
            'FROM "fact_sales" AS f\n'
            'GROUP BY f."category"'
        ),
        field_sql_map={"category": 'f."category"'},
    )
    in_placeholders = ", ".join("?" for _ in plan.tuples)
    oracle = _execute_sqlite_oracle(
        seed_rows=rows,
        sql=(
            'SELECT f."category", SUM(f."amount") AS "metric"\n'
            'FROM "fact_sales" AS f\n'
            f'WHERE f."category" IN ({in_placeholders})\n'
            'GROUP BY f."category"'
        ),
        params=[row[0] for row in plan.tuples],
    )

    assert _normalize_sqlite_rows(result) == _normalize_sqlite_rows(oracle)
    assert _normalize_sqlite_rows(result) == [
        {"category": "Category-0", "product": None, "metric": 1.0},
        {"category": "Category-42", "product": None, "metric": 5.0},
        {"category": "Category-500", "product": None, "metric": 4.0},
    ]


def _assert_case_replays(case: dict[str, Any]) -> None:
    case_type = case["type"]
    if case_type == "pivot-request-contract":
        _assert_pivot_request_contract(case)
    elif case_type == "pivot-translation-contract":
        _assert_pivot_translation_contract(case)
    elif case_type == "domain-renderer-contract":
        _assert_domain_renderer_contract(case)
    elif case_type == "domain-renderer-refusal":
        _assert_domain_renderer_refusal(case)
    elif case_type == "documented-gap":
        _assert_documented_gap(case)
    else:
        raise AssertionError(f"Unsupported pivot/domain case type: {case_type!r}")


def _case_by_id(snapshot: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in snapshot.get("cases", []):
        if case.get("id") == case_id:
            return case
    raise AssertionError(f"Missing Java pivot/domain snapshot case: {case_id}")


def _assert_pivot_request_contract(case: dict[str, Any]) -> None:
    request = SemanticQueryRequest(**case["request"])
    assert request.pivot is not None
    pivot = request.pivot
    expected = case["expected"]

    assert [_axis_name(item) for item in pivot.rows] == expected["rowFields"]
    assert [_axis_name(item) for item in pivot.columns] == expected["columnFields"]
    assert _native_metric_names(pivot.metrics) == expected["nativeMetrics"]
    assert _sql_metric_names(pivot.metrics) == expected["sqlMetrics"]
    assert _all_output_metric_names(pivot.metrics) == expected["allOutputMetrics"]
    assert _derived_metric_names(pivot.metrics, "parentShare") == expected[
        "parentShareMetrics"
    ]
    assert _derived_metric_names(pivot.metrics, "baselineRatio") == expected[
        "baselineRatioMetrics"
    ]
    assert pivot.output_format == expected["outputFormat"]
    assert len(pivot.rows) == expected["rowLevelCount"]
    assert len(pivot.columns) == expected["columnLevelCount"]
    assert pivot.options.grand_total is expected["grandTotal"]
    assert pivot.layout.metric_placement == expected["metricPlacement"]


def _assert_pivot_translation_contract(case: dict[str, Any]) -> None:
    request = SemanticQueryRequest(**case["request"])
    (
        translated,
        want_grand_total,
        parent_share_metrics,
        baseline_ratio_metrics,
    ) = validate_and_translate_pivot(request)

    expected = case["expected"]
    assert translated.pivot is None
    assert translated.group_by == expected["translatedGroupBy"]
    assert translated.columns == expected["translatedColumns"]
    assert want_grand_total is expected["wantGrandTotal"]
    assert [metric.name for metric in parent_share_metrics] == expected[
        "parentShareMetricNames"
    ]
    expected_baseline_ratio_metrics = expected.get("baselineRatioMetricNames", [])
    assert [metric.name for metric in baseline_ratio_metrics] == expected_baseline_ratio_metrics


def _assert_domain_renderer_contract(case: dict[str, Any]) -> None:
    renderer = _renderer_from(case["renderer"])
    plan = _plan_from(case["plan"])
    fragment = renderer.render(plan)
    expected = case["pythonExpected"]

    assert fragment.placement == expected["placement"]
    for marker in expected.get("sqlMarkers", []):
        assert marker in fragment.cte_sql, (
            f"[{case['id']}] SQL marker missing: {marker}\n{fragment.cte_sql}"
        )
    assert len(fragment.domain_params) == expected["paramCount"]
    if "params" in expected:
        assert list(fragment.domain_params) == expected["params"]

    join_sql = build_join_predicate(fragment, _field_sql_map(case), renderer)
    for marker in expected.get("joinPredicateMarkers", []):
        assert marker in join_sql, (
            f"[{case['id']}] predicate marker missing: {marker}\n{join_sql}"
        )


def _assert_domain_renderer_refusal(case: dict[str, Any]) -> None:
    renderer = _renderer_from(case["renderer"])
    plan = _plan_from(case["plan"])
    with pytest.raises(NotImplementedError) as exc_info:
        renderer.render(plan)

    message = str(exc_info.value)
    for marker in case["pythonExpected"].get("messageMarkers", []):
        assert marker in message


def _assert_documented_gap(case: dict[str, Any]) -> None:
    assert case["parityGap"]
    expected = case["pythonExpected"]
    assert expected["status"] in {"refused", "renderer-refused"}

    if expected["status"] == "renderer-refused":
        renderer = _renderer_from(case["renderer"])
        plan = _plan_from(case["plan"])
        with pytest.raises(NotImplementedError) as exc_info:
            renderer.render(plan)
        message = str(exc_info.value)
        for marker in expected.get("messageMarkers", []):
            assert marker in message
        return

    class _Mysql57Dialect:
        name = "mysql5.7"

    with pytest.raises(NotImplementedError) as exc_info:
        resolve_renderer(_Mysql57Dialect())

    message = str(exc_info.value)
    assert PIVOT_DOMAIN_TRANSPORT_REFUSED in message
    for marker in expected.get("messageMarkers", []):
        assert marker in message


def _axis_name(item: str | PivotAxisField) -> str:
    if isinstance(item, str):
        return item
    return item.field


def _native_metric_names(items: list[str | PivotMetricItem]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif item.type == "native":
            out.append(item.name)
    return out


def _sql_metric_names(items: list[str | PivotMetricItem]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            if item not in out:
                out.append(item)
        elif item.type in {"parentShare", "baselineRatio"} and item.of not in out:
            out.append(item.of)
        elif item.type == "native" and item.name not in out:
            out.append(item.name)
    return out


def _all_output_metric_names(items: list[str | PivotMetricItem]) -> list[str]:
    return [item if isinstance(item, str) else item.name for item in items]


def _derived_metric_names(
    items: list[str | PivotMetricItem],
    metric_type: str,
) -> list[str]:
    return [
        item.name
        for item in items
        if isinstance(item, PivotMetricItem) and item.type == metric_type
    ]


def _plan_from(node: dict[str, Any]) -> DomainTransportPlan:
    return DomainTransportPlan(
        columns=tuple(node["fields"]),
        tuples=tuple(tuple(row) for row in node["tuples"]),
    )


def _renderer_from(name: str):
    if name == "postgres":
        return PostgresCteDomainRenderer()
    if name == "sqlite":
        return SqliteCteDomainRenderer()
    if name == "mysql8":
        return Mysql8DomainRenderer()
    raise AssertionError(f"Unsupported Python renderer in P0-7 replay: {name!r}")


def _field_sql_map(case: dict[str, Any]) -> dict[str, str]:
    if case["dialect"] == "mysql":
        return {field: f"_base.`{field}`" for field in case["plan"]["fields"]}
    return {field: f'_base."{field}"' for field in case["plan"]["fields"]}


def _execute_sqlite_domain_transport(
    *,
    plan: DomainTransportPlan,
    seed_rows: list[tuple[str | None, str | None, float]],
    select_sql: str,
    field_sql_map: dict[str, str],
) -> list[dict[str, Any]]:
    renderer = SqliteCteDomainRenderer()
    fragment = renderer.render(plan)
    sql, params = assemble_domain_transport_sql(
        select_sql,
        [],
        fragment,
        field_sql_map,
        renderer,
    )
    return _execute_sqlite_oracle(seed_rows=seed_rows, sql=sql, params=params)


def _execute_sqlite_oracle(
    *,
    seed_rows: list[tuple[str | None, str | None, float]],
    sql: str,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> list[dict[str, Any]]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            CREATE TABLE fact_sales (
                category TEXT,
                product TEXT,
                amount REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO fact_sales(category, product, amount) VALUES (?, ?, ?)",
            seed_rows,
        )
        cursor = conn.execute(sql, list(params or []))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _normalize_sqlite_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "category": row.get("category"),
                "product": row.get("product"),
                "metric": float(row["metric"]) if row.get("metric") is not None else None,
            }
        )
    return sorted(
        normalized,
        key=lambda item: (
            item["category"] is None,
            "" if item["category"] is None else item["category"],
            item["product"] is None,
            "" if item["product"] is None else item["product"],
        ),
    )
