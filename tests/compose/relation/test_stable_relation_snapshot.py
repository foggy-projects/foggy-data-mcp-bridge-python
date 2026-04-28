"""S7a · Consume and validate Java stable relation schema snapshot.

Reads ``_stable_relation_schema_snapshot.json`` produced by Java
``StableRelationSnapshotTest`` and validates contract version, schema
metadata, capabilities, SQL markers, and fail-closed constraints.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    / "_stable_relation_schema_snapshot.json"
)


def _load_snapshot():
    if not _SNAPSHOT_PATH.exists():
        pytest.skip(
            f"Java snapshot not found at {_SNAPSHOT_PATH}. "
            f"Run: mvn test -pl foggy-dataset-model "
            f'-Dtest=StableRelationSnapshotTest in Java repo first.'
        )
    with open(_SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestSnapshotContract:
    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()

    def test_contract_version(self):
        assert self.snapshot["contractVersion"] == "S7a-1"

    def test_source(self):
        assert self.snapshot["source"] == "StableRelationSnapshotTest"

    def test_cases_count(self):
        assert len(self.snapshot["cases"]) == 12, \
            "expected 4 dialects × 3 shapes = 12 cases"


class TestSnapshotSchemaMetadata:
    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in self.snapshot["cases"]}

    def test_yoy_mysql8_schema(self):
        case = self.cases["timewindow-yoy-relation-mysql8"]
        schema = case["relation"]["outputSchema"]
        names = [col["name"] for col in schema]

        # Must include dimension, metric, and derived columns
        assert "storeName" in names
        assert "salesAmount" in names
        assert "salesAmount__prior" in names
        assert "salesAmount__diff" in names
        assert "salesAmount__ratio" in names

        # Validate semantic kinds
        by_name = {col["name"]: col for col in schema}
        assert by_name["storeName"]["semanticKind"] == SemanticKind.BASE_FIELD
        assert by_name["salesAmount"]["semanticKind"] == SemanticKind.AGGREGATE_MEASURE
        assert by_name["salesAmount__prior"]["semanticKind"] == SemanticKind.TIME_WINDOW_DERIVED
        assert by_name["salesAmount__ratio"]["semanticKind"] == SemanticKind.TIME_WINDOW_DERIVED

    def test_ratio_not_aggregatable(self):
        case = self.cases["timewindow-yoy-relation-mysql8"]
        schema = case["relation"]["outputSchema"]
        by_name = {col["name"]: col for col in schema}
        ratio_policy = by_name["salesAmount__ratio"].get("referencePolicy", [])
        assert "aggregatable" not in ratio_policy, \
            "__ratio must NOT include aggregatable"

    def test_derived_columns_have_lineage(self):
        case = self.cases["timewindow-yoy-relation-mysql8"]
        schema = case["relation"]["outputSchema"]
        by_name = {col["name"]: col for col in schema}
        prior = by_name["salesAmount__prior"]
        assert "salesAmount" in prior.get("lineage", [])

    def test_rolling_mysql8_schema(self):
        case = self.cases["timewindow-rolling-relation-mysql8"]
        schema = case["relation"]["outputSchema"]
        names = [col["name"] for col in schema]
        assert "salesAmount__rolling_7d" in names
        by_name = {col["name"]: col for col in schema}
        assert by_name["salesAmount__rolling_7d"]["semanticKind"] == \
               SemanticKind.TIME_WINDOW_DERIVED

    def test_cumulative_mysql8_schema(self):
        case = self.cases["timewindow-cumulative-relation-mysql8"]
        schema = case["relation"]["outputSchema"]
        names = [col["name"] for col in schema]
        assert "salesAmount__ytd" in names


class TestSnapshotCapabilities:
    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in self.snapshot["cases"]}

    def test_yoy_mysql8_capabilities(self):
        case = self.cases["timewindow-yoy-relation-mysql8"]
        caps = case["relation"]["capabilities"]
        assert caps["containsWithItems"] is True
        assert caps["canHoistCte"] is True
        assert caps["supportsOuterAggregate"] is False
        assert caps["supportsOuterWindow"] is False

    def test_rolling_mysql8_has_no_cte(self):
        case = self.cases["timewindow-rolling-relation-mysql8"]
        caps = case["relation"]["capabilities"]
        assert caps["containsWithItems"] is False
        assert caps["canInlineAsSubquery"] is True

    def test_sqlserver_yoy_requires_top_level_with(self):
        case = self.cases["timewindow-yoy-relation-sqlserver"]
        caps = case["relation"]["capabilities"]
        # SQL Server with CTE items is hoisted_cte
        rel = case["relation"]
        assert rel["wrapStrategy"] == RelationWrapStrategy.HOISTED_CTE

    def test_all_cases_outer_capabilities_closed(self):
        """S7a: supportsOuterAggregate and supportsOuterWindow are NEVER true."""
        for case in self.snapshot["cases"]:
            caps = case["relation"]["capabilities"]
            assert caps["supportsOuterAggregate"] is False, \
                f"outer aggregate must be false for {case['id']}"
            assert caps["supportsOuterWindow"] is False, \
                f"outer window must be false for {case['id']}"


class TestSnapshotSqlMarkers:
    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()

    def test_forbidden_sql_markers(self):
        """No case should allow FROM (WITH as a SQL marker."""
        for case in self.snapshot["cases"]:
            forbidden = case.get("forbiddenSqlMarkers", [])
            assert "FROM (WITH" in forbidden, \
                f"case {case['id']} must forbid FROM (WITH"


class TestPythonCapabilitiesParity:
    """Verify Python for_dialect() produces same strategy as Java snapshot."""

    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in self.snapshot["cases"]}

    def test_parity_all_cases(self):
        for case in self.snapshot["cases"]:
            dialect = case["dialect"]
            java_strategy = case["relation"]["wrapStrategy"]
            java_caps = case["relation"]["capabilities"]
            has_with = java_caps["containsWithItems"]

            py_caps = RelationCapabilities.for_dialect(dialect, has_with)
            assert py_caps.relation_wrap_strategy == java_strategy, (
                f"Python for_dialect({dialect!r}, {has_with}) = "
                f"{py_caps.relation_wrap_strategy} but Java = {java_strategy} "
                f"for case {case['id']}"
            )
            assert py_caps.can_hoist_cte == java_caps["canHoistCte"]
            assert py_caps.can_inline_as_subquery == java_caps["canInlineAsSubquery"]
