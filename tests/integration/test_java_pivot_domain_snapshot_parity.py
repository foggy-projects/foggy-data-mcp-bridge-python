"""Replay Java P0-7 pivot/domain transport neutral snapshots.

The lane intentionally stays offline: Pivot DTO/translation shape and domain
transport renderer contracts are checked without Odoo models or live DBs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.pivot.domain_transport import (
    PIVOT_DOMAIN_TRANSPORT_REFUSED,
    DomainTransportPlan,
    Mysql8DomainRenderer,
    PostgresCteDomainRenderer,
    SqliteCteDomainRenderer,
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
