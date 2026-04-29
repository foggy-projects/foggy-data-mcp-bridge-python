"""S7f · Consume and validate Java stable relation outer window snapshot.

Reads ``_stable_relation_outer_window_snapshot.json`` produced by Java
``StableRelationOuterWindowSnapshotTest`` and validates contract version,
capabilities, SQL markers, schema metadata, error codes, and fail-closed
constraints.

S7f opens outer window for wrappable window-capable dialects while keeping
MySQL 5.7 fail-closed for window functions.  The S7a and S7e snapshots remain
frozen; this test consumes the separate ``S7f-1`` snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foggy.dataset_model.engine.compose.compilation import error_codes
from foggy.dataset_model.engine.compose.relation.constants import (
    ReferencePolicy,
    RelationWrapStrategy,
    SemanticKind,
)
from foggy.dataset_model.engine.compose.relation.models import (
    RelationCapabilities,
)

# Relative path from Python repo root to the Java-generated snapshot
_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[4]   # foggy-data-mcp (workspace root)
    / "foggy-data-mcp-bridge-wt-dev-compose"
    / "foggy-dataset-model"
    / "target"
    / "parity"
    / "_stable_relation_outer_window_snapshot.json"
)


def _load_snapshot():
    if not _SNAPSHOT_PATH.exists():
        pytest.skip(
            f"Java S7f snapshot not found at {_SNAPSHOT_PATH}. "
            f"Run: mvn test -pl foggy-dataset-model "
            f'-Dtest=StableRelationOuterWindowSnapshotTest in Java repo first.'
        )
    with open(_SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestS7fSnapshotContract:
    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()

    def test_contract_version(self):
        assert self.snapshot["contractVersion"] == "S7f-1"

    def test_source(self):
        assert self.snapshot["source"] == "StableRelationOuterWindowSnapshotTest"

    def test_cases_count(self):
        assert len(self.snapshot["cases"]) == 5, "expected 5 S7f window cases"


class TestOuterRankRatioOrderMysql8:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.case = {c["id"]: c for c in snapshot["cases"]}[
            "outer-rank-ratio-order-mysql8"
        ]

    def test_status_pass(self):
        assert self.case["status"] == "pass"

    def test_ratio_can_be_order_key(self):
        sql = self.case["sql"]
        assert "RANK()" in sql
        assert "OVER" in sql
        assert "ORDER BY" in sql
        assert "salesAmount__ratio" in sql
        assert "growthRank" in sql

    def test_growth_rank_schema(self):
        by_name = {col["name"]: col for col in self.case["outputSchema"]}
        growth_rank = by_name["growthRank"]
        assert growth_rank["semanticKind"] == SemanticKind.WINDOW_CALC
        assert growth_rank["referencePolicy"] == [
            ReferencePolicy.READABLE,
            ReferencePolicy.ORDERABLE,
        ]
        assert "salesAmount__ratio" in growth_rank["lineage"]
        assert "rank ordered by salesAmount__ratio DESC" == growth_rank["valueMeaning"]

    def test_ratio_not_window_input_by_policy(self):
        assert ReferencePolicy.WINDOWABLE not in ReferencePolicy.TIME_WINDOW_DERIVED_DEFAULT


class TestOuterMovingAvgMeasureMysql8:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.case = {c["id"]: c for c in snapshot["cases"]}[
            "outer-moving-avg-measure-mysql8"
        ]

    def test_status_pass(self):
        assert self.case["status"] == "pass"

    def test_window_sql_markers(self):
        sql = self.case["sql"]
        for marker in ("AVG", "OVER", "PARTITION BY", "ORDER BY", "ROWS BETWEEN"):
            assert marker in sql

    def test_measure_default_is_windowable(self):
        assert ReferencePolicy.WINDOWABLE in ReferencePolicy.MEASURE_DEFAULT

    def test_output_schema(self):
        schema = self.case["outputSchema"]
        assert len(schema) == 1
        moving_avg = schema[0]
        assert moving_avg["name"] == "movingAvg"
        assert moving_avg["semanticKind"] == SemanticKind.WINDOW_CALC
        assert moving_avg["referencePolicy"] == [
            ReferencePolicy.READABLE,
            ReferencePolicy.ORDERABLE,
        ]
        assert moving_avg["lineage"] == ["salesAmount", "storeName", "salesDate"]


class TestOuterWindowRatioInputRejected:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.case = {c["id"]: c for c in snapshot["cases"]}[
            "outer-window-ratio-input-rejected-mysql8"
        ]

    def test_status_rejected(self):
        assert self.case["status"] == "rejected"

    def test_error_code(self):
        assert self.case["errorCode"] == error_codes.RELATION_COLUMN_NOT_WINDOWABLE

    def test_error_phase(self):
        assert self.case["errorPhase"] == "relation-compile"


class TestOuterWindowMysql57Rejected:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.case = {c["id"]: c for c in snapshot["cases"]}[
            "outer-window-mysql57-rejected"
        ]

    def test_status_rejected(self):
        assert self.case["status"] == "rejected"

    def test_error_code(self):
        assert self.case["errorCode"] == error_codes.RELATION_OUTER_WINDOW_NOT_SUPPORTED

    def test_capability_closed(self):
        caps = self.case["capabilities"]
        assert caps["supportsOuterAggregate"] is True
        assert caps["supportsOuterWindow"] is False
        assert caps["wrapStrategy"] == RelationWrapStrategy.INLINE_SUBQUERY


class TestOuterWindowHoistedSqlServer:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.case = {c["id"]: c for c in snapshot["cases"]}[
            "outer-window-hoisted-sqlserver"
        ]

    def test_status_pass(self):
        assert self.case["status"] == "pass"

    def test_hoisted_sqlserver_cte(self):
        sql = self.case["sql"]
        assert sql.startswith(";WITH")
        assert "ROW_NUMBER()" in sql
        assert "FROM rel_0" in sql
        assert "FROM (WITH" not in sql.upper()

    def test_params_order(self):
        assert self.case["params"] == ["p0", "p1"]

    def test_capabilities(self):
        caps = self.case["capabilities"]
        assert caps["containsWithItems"] is True
        assert caps["canHoistCte"] is True
        assert caps["canInlineAsSubquery"] is False
        assert caps["supportsOuterAggregate"] is True
        assert caps["supportsOuterWindow"] is True
        assert caps["wrapStrategy"] == RelationWrapStrategy.HOISTED_CTE


class TestS7fCrossCaseInvariants:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.snapshot = _load_snapshot()

    def test_pass_cases_forbid_from_with(self):
        for case in self.snapshot["cases"]:
            if case["status"] != "pass":
                continue
            assert "FROM (WITH" in case.get("forbiddenSqlMarkers", [])
            assert "FROM (WITH" not in case["sql"].upper()

    def test_pass_cases_support_outer_window(self):
        for case in self.snapshot["cases"]:
            if case["status"] == "pass":
                assert case["capabilities"]["supportsOuterWindow"] is True

    def test_window_outputs_are_not_windowable_or_aggregatable(self):
        for case in self.snapshot["cases"]:
            if case["status"] != "pass":
                continue
            for col in case.get("outputSchema", []):
                if col.get("semanticKind") == SemanticKind.WINDOW_CALC:
                    policy = col.get("referencePolicy", [])
                    assert ReferencePolicy.READABLE in policy
                    assert ReferencePolicy.ORDERABLE in policy
                    assert ReferencePolicy.WINDOWABLE not in policy
                    assert ReferencePolicy.AGGREGATABLE not in policy


class TestS7fPythonCapabilitiesParity:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.snapshot = _load_snapshot()

    def test_parity_all_cases(self):
        for case in self.snapshot["cases"]:
            dialect = case["dialect"]
            java_caps = case["capabilities"]
            has_with = java_caps["containsWithItems"]

            py_caps = RelationCapabilities.for_dialect(dialect, has_with)

            assert py_caps.relation_wrap_strategy == java_caps["wrapStrategy"]
            assert py_caps.can_hoist_cte == java_caps["canHoistCte"]
            assert py_caps.can_inline_as_subquery == java_caps["canInlineAsSubquery"]
            assert py_caps.supports_outer_aggregate == java_caps["supportsOuterAggregate"]
            assert py_caps.supports_outer_window == java_caps["supportsOuterWindow"]
