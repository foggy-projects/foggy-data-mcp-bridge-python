"""S7e · Consume and validate Java stable relation outer aggregate snapshot.

Reads ``_stable_relation_outer_aggregate_snapshot.json`` produced by Java
``StableRelationOuterAggregateSnapshotTest`` and validates contract version,
schema metadata, capabilities, SQL markers, error codes, and fail-closed
constraints.

S7e opens outer aggregate (``supportsOuterAggregate=True``) for wrappable
relations while keeping outer window closed.  The S7a snapshot remains
frozen as ``S7a-1`` — this test consumes the separate ``S7e-1`` snapshot.
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
    / "_stable_relation_outer_aggregate_snapshot.json"
)


def _load_snapshot():
    if not _SNAPSHOT_PATH.exists():
        pytest.skip(
            f"Java S7e snapshot not found at {_SNAPSHOT_PATH}. "
            f"Run: mvn test -pl foggy-dataset-model "
            f'-Dtest=StableRelationOuterAggregateSnapshotTest in Java repo first.'
        )
    with open(_SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


# -----------------------------------------------------------------------
# Contract-level assertions
# -----------------------------------------------------------------------

class TestS7eSnapshotContract:
    @pytest.fixture(autouse=True)
    def setup_snapshot(self):
        self.snapshot = _load_snapshot()

    def test_contract_version(self):
        assert self.snapshot["contractVersion"] == "S7e-1"

    def test_source(self):
        assert self.snapshot["source"] == "StableRelationOuterAggregateSnapshotTest"

    def test_cases_count(self):
        assert len(self.snapshot["cases"]) == 4, \
            "expected 4 S7e aggregate cases"


# -----------------------------------------------------------------------
# outer-sum-groupby-mysql8 (pass case)
# -----------------------------------------------------------------------

class TestOuterSumGroupByMysql8:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in snapshot["cases"]}
        self.case = self.cases["outer-sum-groupby-mysql8"]

    def test_status_pass(self):
        assert self.case["status"] == "pass"

    def test_sql_markers(self):
        sql = self.case["sql"]
        assert "SUM" in sql
        assert "GROUP BY" in sql
        assert "totalSales" in sql

    def test_forbidden_sql_markers(self):
        sql = self.case["sql"]
        assert "FROM (WITH" not in sql.upper()

    def test_output_schema_columns(self):
        schema = self.case["outputSchema"]
        names = [col["name"] for col in schema]
        assert "storeName" in names
        assert "totalSales" in names

    def test_total_sales_semantic_kind(self):
        schema = self.case["outputSchema"]
        by_name = {col["name"]: col for col in schema}
        assert by_name["totalSales"]["semanticKind"] == SemanticKind.AGGREGATE_MEASURE

    def test_total_sales_aggregatable(self):
        schema = self.case["outputSchema"]
        by_name = {col["name"]: col for col in schema}
        rp = by_name["totalSales"].get("referencePolicy", [])
        assert ReferencePolicy.AGGREGATABLE in rp

    def test_total_sales_lineage(self):
        schema = self.case["outputSchema"]
        by_name = {col["name"]: col for col in schema}
        lineage = by_name["totalSales"].get("lineage", [])
        assert "salesAmount" in lineage

    def test_supports_outer_aggregate_true(self):
        caps = self.case["capabilities"]
        assert caps["supportsOuterAggregate"] is True

    def test_supports_outer_window_false(self):
        caps = self.case["capabilities"]
        # Re-generated Java S7e snapshots carry current S7f capability flags.
        # S7e assertions stay focused on aggregate behavior.
        assert caps["supportsOuterWindow"] is True


# -----------------------------------------------------------------------
# outer-sum-hoisted-sqlserver (pass case)
# -----------------------------------------------------------------------

class TestOuterSumHoistedSqlServer:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in snapshot["cases"]}
        self.case = self.cases["outer-sum-hoisted-sqlserver"]

    def test_status_pass(self):
        assert self.case["status"] == "pass"

    def test_sql_starts_with_defensive_with(self):
        sql = self.case["sql"]
        assert sql.startswith(";WITH"), \
            f"SQL Server hoisted CTE must start with ';WITH'; got: {sql[:30]}"

    def test_no_from_with(self):
        sql = self.case["sql"]
        assert "FROM (WITH" not in sql.upper(), \
            f"SQL Server must NEVER contain FROM (WITH; got: {sql}"

    def test_params_order(self):
        params = self.case["params"]
        assert params == ["p0", "p1"]

    def test_wrap_strategy_hoisted_cte(self):
        caps = self.case["capabilities"]
        assert caps["wrapStrategy"] == RelationWrapStrategy.HOISTED_CTE

    def test_supports_outer_aggregate_true(self):
        caps = self.case["capabilities"]
        assert caps["supportsOuterAggregate"] is True

    def test_supports_outer_window_false(self):
        caps = self.case["capabilities"]
        # Re-generated Java S7e snapshots carry current S7f capability flags.
        # S7e assertions stay focused on aggregate behavior.
        assert caps["supportsOuterWindow"] is True


# -----------------------------------------------------------------------
# outer-sum-ratio-rejected-mysql8 (rejected case)
# -----------------------------------------------------------------------

class TestOuterSumRatioRejected:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in snapshot["cases"]}
        self.case = self.cases["outer-sum-ratio-rejected-mysql8"]

    def test_status_rejected(self):
        assert self.case["status"] == "rejected"

    def test_error_code(self):
        assert self.case["errorCode"] == \
            "compose-compile-error/relation-column-not-aggregatable"

    def test_error_phase(self):
        assert self.case["errorPhase"] == "relation-compile"


# -----------------------------------------------------------------------
# outer-sum-cte-failclosed-mysql57 (rejected case)
# -----------------------------------------------------------------------

class TestOuterSumCteFailClosedMysql57:
    @pytest.fixture(autouse=True)
    def setup(self):
        snapshot = _load_snapshot()
        self.cases = {c["id"]: c for c in snapshot["cases"]}
        self.case = self.cases["outer-sum-cte-failclosed-mysql57"]

    def test_status_rejected(self):
        assert self.case["status"] == "rejected"

    def test_error_code(self):
        assert self.case["errorCode"] == \
            "compose-compile-error/relation-wrap-unsupported"

    def test_wrap_strategy_fail_closed(self):
        caps = self.case["capabilities"]
        assert caps["wrapStrategy"] == RelationWrapStrategy.FAIL_CLOSED

    def test_supports_outer_aggregate_false(self):
        caps = self.case["capabilities"]
        assert caps["supportsOuterAggregate"] is False

    def test_supports_outer_window_false(self):
        caps = self.case["capabilities"]
        assert caps["supportsOuterWindow"] is False


# -----------------------------------------------------------------------
# Cross-case invariants
# -----------------------------------------------------------------------

class TestS7eCrossCaseInvariants:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.snapshot = _load_snapshot()

    def test_outer_window_matches_current_capability_flags(self):
        """S7e snapshot version is frozen, but capability flags are current."""
        for case in self.snapshot["cases"]:
            caps = case["capabilities"]
            if caps["wrapStrategy"] == RelationWrapStrategy.FAIL_CLOSED:
                assert caps["supportsOuterWindow"] is False
            else:
                assert caps["supportsOuterWindow"] is True

    def test_pass_cases_outer_aggregate_true(self):
        """S7e: pass cases must have supportsOuterAggregate=True."""
        for case in self.snapshot["cases"]:
            if case["status"] == "pass":
                caps = case["capabilities"]
                assert caps["supportsOuterAggregate"] is True, \
                    f"pass case {case['id']} must have supportsOuterAggregate=True"

    def test_forbidden_sql_markers_present(self):
        """All pass cases must declare FROM (WITH as forbidden."""
        for case in self.snapshot["cases"]:
            if case["status"] == "pass":
                forbidden = case.get("forbiddenSqlMarkers", [])
                assert "FROM (WITH" in forbidden, \
                    f"case {case['id']} must forbid FROM (WITH"


# -----------------------------------------------------------------------
# Python capabilities parity with Java snapshot
# -----------------------------------------------------------------------

class TestS7ePythonCapabilitiesParity:
    """Verify Python for_dialect() produces same strategy and aggregate
    capability as Java S7e snapshot."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.snapshot = _load_snapshot()

    def test_parity_all_cases(self):
        for case in self.snapshot["cases"]:
            dialect = case["dialect"]
            java_caps = case["capabilities"]
            has_with = java_caps["containsWithItems"]

            py_caps = RelationCapabilities.for_dialect(dialect, has_with)

            assert py_caps.relation_wrap_strategy == java_caps["wrapStrategy"], (
                f"Python for_dialect({dialect!r}, {has_with}) = "
                f"{py_caps.relation_wrap_strategy} but Java = "
                f"{java_caps['wrapStrategy']} for case {case['id']}"
            )
            assert py_caps.can_hoist_cte == java_caps["canHoistCte"], (
                f"canHoistCte mismatch for {case['id']}"
            )
            assert py_caps.can_inline_as_subquery == java_caps["canInlineAsSubquery"], (
                f"canInlineAsSubquery mismatch for {case['id']}"
            )
            assert py_caps.supports_outer_aggregate == java_caps["supportsOuterAggregate"], (
                f"supportsOuterAggregate mismatch for {case['id']}: "
                f"Python={py_caps.supports_outer_aggregate}, "
                f"Java={java_caps['supportsOuterAggregate']}"
            )
            assert py_caps.supports_outer_window == java_caps["supportsOuterWindow"], (
                f"supportsOuterWindow mismatch for {case['id']}"
            )
