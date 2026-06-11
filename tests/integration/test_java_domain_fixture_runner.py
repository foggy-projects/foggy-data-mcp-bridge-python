"""Replay Java P0-31 domain/question neutral runner fixtures.

The lane intentionally skips LLM and Odoo business packs. Java exports
normalized MCP tool arguments; Python replays those arguments through a
deterministic semantic boundary so the engine request contract is executable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from foggy.dataset_model.semantic.pivot.flat_executor import (
    PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest, SemanticQueryResponse
from foggy.mcp_spi.accessor import build_query_request

DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_domain_question_neutral_runner_parity.json"
)
SNAPSHOT_PATH = Path(
    os.environ.get("FOGGY_DOMAIN_QUESTION_NEUTRAL_FIXTURE", DEFAULT_SNAPSHOT_PATH)
)


def _load_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            "Java domain/question neutral runner export not available yet: "
            f"{SNAPSHOT_PATH}. P0-31 activates once the Java exporter writes "
            "engine-neutral normalized tool-argument fixtures.",
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_schema() -> None:
    snapshot = _load_snapshot()
    assert snapshot["schemaVersion"] == 1
    assert snapshot["feature"] == "domainQuestionNeutralRunner"
    assert snapshot["source"] == "JavaDomainQuestionNeutralRunnerSnapshotTest"
    assert snapshot["contract"] == "normalized-tool-arguments-v1"
    assert snapshot.get("cases")


def test_java_domain_question_neutral_runner_replays_in_python() -> None:
    snapshot = _load_snapshot()
    boundary = _NeutralSemanticBoundary()
    for case in snapshot.get("cases", []):
        _assert_case_replays(case, boundary)


def test_pivot_time_window_unsupported_fixture_fails_closed_in_python_service() -> None:
    snapshot = _load_snapshot()
    case = _case_by_id(snapshot, "pivot-time-window-mutual-exclusion-unsupported")
    tool_arguments = case["expected"]["toolArguments"]
    request = build_query_request(tool_arguments["payload"])

    service = SemanticQueryService()
    service.register_model(create_fact_sales_model())
    response = service.query_model(
        tool_arguments["model"],
        request,
        mode=tool_arguments["mode"],
    )

    assert response.error is not None
    assert PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON in response.error
    assert "pivot + timeWindow" in response.error
    assert "FIELD_NOT_FOUND" not in response.error
    assert "orderDate" not in response.error


def _case_by_id(snapshot: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in snapshot.get("cases", []):
        if case.get("id") == case_id:
            return case
    pytest.fail(f"Missing case {case_id!r} in {SNAPSHOT_PATH}")


def _assert_case_replays(
    case: dict[str, Any],
    boundary: _NeutralSemanticBoundary,
) -> None:
    expected = case["expected"]
    assert expected["toolName"] == "dataset.query_model"

    tool_arguments = expected["toolArguments"]
    assert tool_arguments["model"] == "FactSalesModel"
    assert tool_arguments["mode"] in {"execute", "validate"}

    payload = tool_arguments["payload"]
    request = build_query_request(payload)
    _assert_payload_round_trips(payload, request)

    error_code = expected.get("errorCode")
    _assert_collector_record(expected)
    if error_code:
        response = boundary.query_model(
            tool_arguments["model"],
            request,
            mode=tool_arguments["mode"],
            case=case,
        )
        assert response.error is not None
        assert response.error_detail is not None
        assert response.error_detail["code"] == error_code
        _assert_unsupported_constructs(expected, response)
        for marker in expected.get("warnings", []):
            assert marker in (response.warnings or [])
        _assert_reports_metadata(expected, response)
        _assert_forbidden_markers_absent(response.model_dump(), expected)
        return

    response = boundary.query_model(
        tool_arguments["model"],
        request,
        mode=tool_arguments["mode"],
        case=case,
    )
    assert response.error is None
    assert response.sql is not None
    for marker in expected.get("sqlMarkers", []):
        assert marker in response.sql
    response_text = json.dumps(
        response.model_dump(by_alias=True, exclude_none=True),
        sort_keys=True,
    )
    for marker in expected.get("resultMarkers", []):
        assert marker in response_text
    for marker in expected.get("warnings", []):
        assert marker in (response.warnings or [])
    _assert_reports_metadata(expected, response)
    _assert_forbidden_markers_absent(response.model_dump(), expected)


def _assert_collector_record(expected: dict[str, Any]) -> None:
    collector = expected.get("collectorRecord")
    assert isinstance(collector, dict)

    error_code = expected.get("errorCode")
    expected_success = error_code is None

    assert collector["sessionId"] == "domain-question-neutral-runner"
    assert collector["callCount"] == 1
    assert collector["allSuccess"] is expected_success
    assert collector["toolName"] == expected["toolName"]
    assert collector["springToolName"] == "dataset_query_model"
    assert collector["arguments"] == expected["toolArguments"]
    assert collector["success"] is expected_success
    assert collector["durationMs"] == 0
    assert collector["sequence"] == 0

    result = collector["result"]
    assert isinstance(result, dict)
    if expected_success:
        assert result["status"] == "ok"
        assert result["rowCount"] == 1
        assert collector["error"] is None
    else:
        assert result["status"] == "error"
        assert result["errorCode"] == error_code
        assert error_code in collector["error"]


def _assert_payload_round_trips(
    payload: dict[str, Any],
    request: SemanticQueryRequest,
) -> None:
    assert request.columns == payload.get("columns", [])
    assert request.group_by == payload.get("groupBy", [])
    assert request.order_by == payload.get("orderBy", [])
    assert request.slice == payload.get("slice", [])
    assert request.calculated_fields == payload.get("calculatedFields", [])
    assert request.start == payload.get("start", 0)
    assert request.limit == payload.get("limit")
    assert request.return_total is payload.get("returnTotal", False)
    assert request.time_window == payload.get("timeWindow")
    assert request.hints == payload.get("hints")
    if "pivot" in payload:
        assert request.pivot is not None
        pivot = request.pivot.model_dump(by_alias=True, exclude_none=True)
        assert pivot["rows"] == payload["pivot"].get("rows", [])
        assert pivot["columns"] == payload["pivot"].get("columns", [])
        assert pivot["metrics"] == payload["pivot"].get("metrics", [])
        assert pivot["outputFormat"] == payload["pivot"].get("outputFormat", "tree")
    if "deniedColumns" in payload:
        assert request.denied_columns is not None
        assert [
            item.model_dump(by_alias=True, exclude_none=True)
            for item in request.denied_columns
        ] == [
            {
                key: value
                for key, value in item.items()
                if key in {"schema", "table", "column"}
            }
            for item in payload["deniedColumns"]
        ]


def _assert_unsupported_constructs(
    expected: dict[str, Any],
    response: SemanticQueryResponse,
) -> None:
    unsupported = expected.get("unsupportedConstructs")
    if unsupported is None:
        return

    assert response.error_detail is not None
    assert response.error_detail.get("unsupportedConstructs") == unsupported


def _assert_forbidden_markers_absent(
    payload: Any,
    expected: dict[str, Any],
) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in expected.get("forbiddenMarkers", []):
        assert marker not in serialized


def _assert_reports_metadata(
    expected: dict[str, Any],
    response: SemanticQueryResponse,
) -> None:
    reports = expected.get("reports")
    if reports is None:
        return

    assert isinstance(reports, list)
    assert len(reports) == 1
    report = reports[0]
    tool_arguments = expected["toolArguments"]
    warnings = response.warnings or []
    error_code = expected.get("errorCode")

    assert report["reportType"] == "neutral-runner-case-summary"
    assert report["toolName"] == expected["toolName"]
    assert report["model"] == tool_arguments["model"]
    assert report["mode"] == tool_arguments["mode"]
    assert report["status"] == ("error" if error_code else "ok")
    assert report["warningCount"] == len(warnings)
    assert report["errorCount"] == (1 if error_code else 0)
    assert report.get("warningMarkers", []) == expected.get("warnings", [])
    if "unsupportedConstructs" in expected:
        assert report["unsupportedConstructs"] == expected["unsupportedConstructs"]
    else:
        assert "unsupportedConstructs" not in report
    if error_code:
        assert report["errorCode"] == error_code
        assert response.error is not None
    else:
        assert "errorCode" not in report
        assert response.error is None


class _NeutralSemanticBoundary:
    def query_model(
        self,
        model: str,
        request: SemanticQueryRequest,
        *,
        mode: str,
        case: dict[str, Any],
    ) -> SemanticQueryResponse:
        assert model == "FactSalesModel"
        assert mode in {"execute", "validate"}

        expected = case["expected"]
        if expected.get("errorCode"):
            return SemanticQueryResponse.from_error(
                "Query rejected by neutral runner governance",
                warnings=list(expected.get("warnings", [])),
                error_detail={
                    "code": expected["errorCode"],
                    "phase": "permission-resolve",
                    "unsupportedConstructs": list(
                        expected.get("unsupportedConstructs", [])
                    ),
                },
            )

        columns = list(request.group_by) + list(request.columns)
        rows = [{name: _sample_value(name) for name in columns}]
        sql = _sql_for(request)
        return SemanticQueryResponse.from_legacy(
            data=rows,
            columns_info=[{"name": name, "dataType": "STRING"} for name in columns],
            total=len(rows),
            sql=sql,
            warnings=list(expected.get("warnings", [])),
            start=request.start,
            limit=request.limit,
        )


def _sample_value(name: str) -> Any:
    if name == "salesAmount":
        return 1200
    if name == "grossMargin":
        return 420
    return name


def _sql_for(request: SemanticQueryRequest) -> str:
    select_parts: list[str] = []
    for field in request.group_by:
        select_parts.append(str(field))
    for field in request.columns:
        if field == "grossMargin":
            select_parts.append("salesAmount - costAmount AS grossMargin")
        else:
            select_parts.append(str(field))
    if not select_parts:
        select_parts.append("*")

    sql = "SELECT " + ", ".join(select_parts) + " FROM fact_sales"
    if request.slice:
        sql += " WHERE " + " AND ".join(str(item.get("field", "slice")) for item in request.slice)
    if request.group_by:
        sql += " GROUP BY " + ", ".join(str(field) for field in request.group_by)
    return sql
