"""Tests to verify Python SPI models produce Java-compatible JSON output.

These tests ensure that the externally-facing JSON format matches
Java's SemanticQueryResponse, SemanticQueryRequest, etc. exactly.
"""

import pytest
from foggy.mcp_spi import (
    ColumnDef,
    SchemaInfo,
    PaginationInfo,
    NormalizedRequest,
    DebugInfo,
    SemanticQueryResponse,
    SemanticQueryRequest,
    SemanticMetadataResponse,
)


class TestSemanticQueryResponseAlignment:
    """Verify SemanticQueryResponse JSON matches Java format."""

    def test_basic_response_fields(self):
        """Response uses 'items' not 'data', 'schema' not 'columns'."""
        resp = SemanticQueryResponse(
            items=[{"name": "test", "amount": 100}],
            schema_info=SchemaInfo(
                columns=[ColumnDef(name="name", data_type="STRING", title="名称")],
                summary="1 row returned",
            ),
            total=1,
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)

        assert "items" in j
        assert "data" not in j  # not the old Python field name
        assert "schema" in j
        assert j["items"] == [{"name": "test", "amount": 100}]
        assert j["total"] == 1

    def test_schema_info_camel_case(self):
        """SchemaInfo.ColumnDef uses 'dataType' not 'data_type'."""
        col = ColumnDef(name="amount", data_type="DECIMAL", title="金额")
        j = col.model_dump(by_alias=True, exclude_none=True)
        assert j["dataType"] == "DECIMAL"
        assert "data_type" not in j

    def test_pagination_camel_case(self):
        """PaginationInfo uses camelCase fields."""
        p = PaginationInfo(
            start=0, limit=100, returned=50,
            total_count=200, has_more=True,
            range_description="显示第 1-50 条，共 200 条",
        )
        j = p.model_dump(by_alias=True, exclude_none=True)
        assert j["totalCount"] == 200
        assert j["hasMore"] is True
        assert j["rangeDescription"] == "显示第 1-50 条，共 200 条"
        assert "total_count" not in j
        assert "has_more" not in j

    def test_debug_info_camel_case(self):
        """DebugInfo uses 'durationMs' not 'duration_ms'."""
        d = DebugInfo(duration_ms=42.5, extra={"sql": "SELECT 1"})
        j = d.model_dump(by_alias=True, exclude_none=True)
        assert j["durationMs"] == 42.5
        assert "duration_ms" not in j

    def test_full_response_matches_java_structure(self):
        """Full response structure matches Java SemanticQueryResponse."""
        resp = SemanticQueryResponse(
            items=[{"product": "Widget", "amount": 100}],
            schema_info=SchemaInfo(
                columns=[
                    ColumnDef(name="product", data_type="TEXT", title="产品"),
                    ColumnDef(name="amount", data_type="DECIMAL", title="金额"),
                ],
            ),
            pagination=PaginationInfo(
                start=0, limit=10, returned=1,
                total_count=1, has_more=False,
            ),
            total=1,
            has_next=False,
            warnings=["test warning"],
            debug=DebugInfo(
                duration_ms=15.3,
                normalized=NormalizedRequest(
                    slice=[{"field": "status", "op": "=", "value": "active"}],
                    group_by=[{"field": "product"}],
                    order_by=[{"field": "amount", "dir": "desc"}],
                ),
            ),
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)

        # Top-level keys match Java
        assert set(j.keys()) == {
            "items", "schema", "pagination", "total",
            "hasNext", "warnings", "debug",
        }
        # Nested camelCase
        assert j["pagination"]["hasMore"] is False
        assert j["pagination"]["totalCount"] == 1
        assert j["debug"]["durationMs"] == 15.3
        assert j["debug"]["normalized"]["groupBy"] == [{"field": "product"}]
        assert j["debug"]["normalized"]["orderBy"] == [{"field": "amount", "dir": "desc"}]

    def test_exclude_none_removes_empty_fields(self):
        """None fields are excluded from output."""
        resp = SemanticQueryResponse(items=[])
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert "schema" not in j  # schema_info is None
        assert "pagination" not in j
        assert "debug" not in j
        assert "cursor" not in j
        assert "totalData" not in j
        assert "hasNext" not in j
        assert "truncationInfo" not in j

    def test_backward_compat_properties(self):
        """Backward compat: .data, .sql, .columns, .metrics still work."""
        resp = SemanticQueryResponse(
            items=[{"a": 1}],
            schema_info=SchemaInfo(columns=[ColumnDef(name="a", data_type="INT")]),
            debug=DebugInfo(duration_ms=10, extra={"sql": "SELECT 1"}),
        )
        # .data returns items
        assert resp.data == [{"a": 1}]
        # .sql from debug
        assert resp.sql == "SELECT 1"
        # .columns from schema_info
        assert len(resp.columns) == 1
        assert resp.columns[0]["name"] == "a"
        # .metrics from debug
        assert resp.metrics["duration_ms"] == 10

    def test_from_legacy_factory(self):
        """from_legacy() creates properly structured response."""
        resp = SemanticQueryResponse.from_legacy(
            data=[{"x": 1}],
            columns_info=[{"name": "x", "dataType": "INT"}],
            total=1,
            sql="SELECT x FROM t",
            duration_ms=5.0,
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert j["items"] == [{"x": 1}]
        assert j["schema"]["columns"][0]["dataType"] == "INT"
        assert j["debug"]["extra"]["sql"] == "SELECT x FROM t"

    def test_from_legacy_with_pagination(self):
        """from_legacy() builds PaginationInfo when limit is provided."""
        resp = SemanticQueryResponse.from_legacy(
            data=[{"a": 1}, {"a": 2}],
            total=10,
            start=0,
            limit=5,
            has_more=True,
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert "pagination" in j
        p = j["pagination"]
        assert p["start"] == 0
        assert p["limit"] == 5
        assert p["returned"] == 2
        assert p["totalCount"] == 10
        assert p["hasMore"] is True
        assert "rangeDescription" in p
        assert p["rangeDescription"] == "第 1-2 条，共 10 条"

    def test_from_legacy_with_pagination_has_more_computed(self):
        """from_legacy() computes hasMore when not explicitly provided."""
        # start=0, returned=2, total=5 → hasMore = True (0+2 < 5)
        resp = SemanticQueryResponse.from_legacy(
            data=[{"a": 1}, {"a": 2}],
            total=5,
            start=0,
            limit=2,
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert j["pagination"]["hasMore"] is True

        # start=3, returned=2, total=5 → hasMore = False (3+2 >= 5)
        resp2 = SemanticQueryResponse.from_legacy(
            data=[{"a": 4}, {"a": 5}],
            total=5,
            start=3,
            limit=2,
        )
        j2 = resp2.model_dump(by_alias=True, exclude_none=True)
        assert j2["pagination"]["hasMore"] is False

    def test_from_legacy_without_limit_no_pagination(self):
        """from_legacy() without limit does not produce pagination (backward compat)."""
        resp = SemanticQueryResponse.from_legacy(
            data=[{"x": 1}],
            total=1,
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert "pagination" not in j

    def test_from_error_factory(self):
        """from_error() creates response with internal error."""
        resp = SemanticQueryResponse.from_error("Model not found: foo")
        assert resp.error == "Model not found: foo"
        assert resp.items == []
        # Error is not in JSON output (internal only)
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert "error" not in j or "_error" not in j

    def test_has_next_and_total_data(self):
        """hasNext and totalData serialize correctly."""
        resp = SemanticQueryResponse(
            items=[{"a": 1}],
            has_next=True,
            total_data={"salesAmount": 1000},
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert j["hasNext"] is True
        assert j["totalData"] == {"salesAmount": 1000}

    def test_truncation_info(self):
        """truncationInfo serializes correctly."""
        resp = SemanticQueryResponse(
            items=[{"a": 1}],
            truncation_info={
                "truncated": True,
                "originalRows": 5000,
                "returnedRows": 100,
                "viewUrl": "https://example.com/view/123",
            },
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert j["truncationInfo"]["truncated"] is True
        assert j["truncationInfo"]["originalRows"] == 5000


class TestSemanticQueryRequestAlignment:
    """Verify SemanticQueryRequest accepts and outputs Java-format JSON."""

    def test_accepts_java_camel_case(self):
        """Request accepts Java camelCase field names."""
        payload = {
            "columns": ["product$caption", "sum(salesAmount)"],
            "slice": [{"field": "salesDate", "op": "[]", "value": ["2024-01-01", "2024-12-31"]}],
            "groupBy": [{"field": "product$caption"}],
            "orderBy": [{"field": "salesAmount", "dir": "desc"}],
            "start": 0,
            "limit": 100,
            "returnTotal": True,
            "captionMatchMode": "EXACT",
            "mismatchHandleStrategy": "ABORT",
            "distinct": False,
            "withSubtotals": False,
        }
        req = SemanticQueryRequest(**payload)
        assert req.columns == ["product$caption", "sum(salesAmount)"]
        assert len(req.slice) == 1
        assert req.slice[0]["field"] == "salesDate"
        assert req.group_by == [{"field": "product$caption"}]
        assert req.order_by == [{"field": "salesAmount", "dir": "desc"}]
        assert req.start == 0
        assert req.limit == 100
        assert req.return_total is True
        assert req.caption_match_mode == "EXACT"
        assert req.mismatch_handle_strategy == "ABORT"

    def test_serializes_to_java_camel_case(self):
        """Request serializes to Java camelCase."""
        req = SemanticQueryRequest(
            columns=["name"],
            slice=[{"field": "status", "op": "=", "value": "A"}],
            group_by=[{"field": "name"}],
            order_by=[{"field": "name", "dir": "asc"}],
            return_total=True,
            with_subtotals=True,
            calculated_fields=[{"name": "ratio", "expression": "a/b"}],
        )
        j = req.model_dump(by_alias=True, exclude_none=True)
        assert "groupBy" in j
        assert "orderBy" in j
        assert "returnTotal" in j
        assert "withSubtotals" in j
        assert "calculatedFields" in j
        # No snake_case keys in output
        assert "group_by" not in j
        assert "order_by" not in j
        assert "return_total" not in j

    def test_populate_by_name_allows_snake_case_attrs(self):
        """Pydantic populate_by_name allows Python snake_case attribute names."""
        req = SemanticQueryRequest(
            columns=["name"],
            group_by=["name"],
            order_by=[{"field": "name"}],
            calculated_fields=[{"name": "x", "expression": "1+1"}],
            return_total=True,
            with_subtotals=True,
        )
        assert req.group_by == ["name"]
        assert req.order_by == [{"field": "name"}]
        assert len(req.calculated_fields) == 1
        assert req.return_total is True
        assert req.with_subtotals is True

    def test_new_fields_present(self):
        """New Java-aligned fields are available."""
        req = SemanticQueryRequest(
            columns=["name"],
            captionMatchMode="FUZZY",
            mismatchHandleStrategy="IGNORE",
            hints={"timeRange": {"from": "2024-01-01"}},
            stream=True,
            cursor="abc123",
        )
        assert req.caption_match_mode == "FUZZY"
        assert req.mismatch_handle_strategy == "IGNORE"
        assert req.hints == {"timeRange": {"from": "2024-01-01"}}
        assert req.stream is True
        assert req.cursor == "abc123"

    def test_calculated_fields_with_window(self):
        """calculatedFields with window function definition."""
        cf = {
            "name": "movingAvg",
            "expression": "salesAmount",
            "agg": "AVG",
            "partitionBy": ["product$caption"],
            "windowOrderBy": [{"field": "salesDate$caption", "dir": "asc"}],
            "windowFrame": "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW",
        }
        req = SemanticQueryRequest(
            columns=["product$caption", "salesDate$caption", "movingAvg"],
            calculatedFields=[cf],
        )
        assert len(req.calculated_fields) == 1
        assert req.calculated_fields[0]["name"] == "movingAvg"


class TestSemanticMetadataResponseAlignment:
    """Verify SemanticMetadataResponse JSON matches Java format."""

    def test_java_format_output(self):
        """Java format: {content, data, format}."""
        resp = SemanticMetadataResponse(
            content="# Model\n...",
            format="markdown",
        )
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert j == {"content": "# Model\n...", "format": "markdown"}
        # Internal fields not in JSON
        assert "models" not in j
        assert "error" not in j
        assert "warnings" not in j

    def test_internal_fields_accessible(self):
        """Internal fields (models, error, warnings) are accessible via properties."""
        resp = SemanticMetadataResponse(models=[{"name": "TestModel"}])
        resp.error = "test error"
        resp.warnings = ["warn1"]
        resp.columns = [{"name": "col1"}]

        assert len(resp.models) == 1
        assert resp.error == "test error"
        assert resp.warnings == ["warn1"]
        assert resp.columns == [{"name": "col1"}]

        # But they don't appear in JSON
        j = resp.model_dump(by_alias=True, exclude_none=True)
        assert "error" not in j
        assert "warnings" not in j


class TestSliceOperators:
    """Verify DSL slice operators are passed through correctly."""

    def test_slice_with_or_group(self):
        """$or group in slice is preserved."""
        payload = {
            "columns": ["name"],
            "slice": [
                {"$or": [
                    {"field": "status", "op": "=", "value": "A"},
                    {"field": "status", "op": "=", "value": "B"},
                ]}
            ],
        }
        req = SemanticQueryRequest(**payload)
        assert len(req.slice) == 1
        assert "$or" in req.slice[0]

    def test_slice_with_range_operators(self):
        """Range operators ([], [), etc.) are preserved."""
        payload = {
            "columns": ["salesDate"],
            "slice": [
                {"field": "salesDate", "op": "[]", "value": ["2024-01-01", "2024-12-31"]},
                {"field": "amount", "op": "[)", "value": [100, 500]},
            ],
        }
        req = SemanticQueryRequest(**payload)
        assert req.slice[0]["op"] == "[]"
        assert req.slice[1]["op"] == "[)"

    def test_slice_with_expr(self):
        """$expr conditions are preserved."""
        payload = {
            "columns": ["name"],
            "slice": [
                {"$expr": "actualAmount > budgetAmount"},
            ],
        }
        req = SemanticQueryRequest(**payload)
        assert req.slice[0]["$expr"] == "actualAmount > budgetAmount"
