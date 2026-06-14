"""Validate the planned Java O615 aggregate-join snapshot contract lane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_querymodel_aggregate_join_o615_snapshot_contract.json"
)
MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_snapshot_parity_manifest.json"
)

REQUIRED_CASE_IDS = {
    "aggregate-join-o615-no-columns-with-access",
    "aggregate-join-o615-explicit-join-no-columns",
    "aggregate-join-o615-tenant-guard-no-leak",
    "aggregate-join-o615-dimension-id-slice",
    "aggregate-join-o615-rhs-dimension-filter",
    "aggregate-join-o615-rhs-join-dimension-filter",
}

REQUIRED_JAVA_TESTS = {
    "aggregateRelationO615ProbeNoColumnsWithAccessShouldResolveJoinPath",
    "aggregateRelationO615ProbeExpressJoinNoColumnsShouldResolveJoinPath",
    "aggregateRelationO615TenantGuardShouldBypassFieldAccessWithoutLeaking",
    "aggregateRelationO615ProbeExpressJoinDimensionIdSliceShouldResolveJoinPath",
    "aggregateRelationO615ProbeRhsDimensionFilterShouldResolveJoinPath",
    "aggregateRelationO615ProbeRhsJoinDimensionFilterShouldResolveJoinPath",
}

REQUIRED_MODELS = {
    "OrderStationStockProjectionO615ProbeQueryModel",
    "OrderStationStockProjectionO615ExpressJoinProbeQueryModel",
    "OrderStationStockProjectionO615RhsDimensionProbeQueryModel",
    "OrderStationStockProjectionO615RhsJoinDimensionProbeQueryModel",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_o615_contract_schema_and_required_cases() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert contract["schemaVersion"] == 1
    assert contract["feature"] == "queryModelAggregateJoin"
    assert contract["status"] == "contractOnly"
    assert contract["source"] == "AggregateJoinQueryModelTest"
    assert contract["contractVersion"] == "querymodel-aggregate-join-4"

    required_envelope = set(contract["requiredEnvelopeFields"])
    assert {"schemaVersion", "feature", "source", "contractVersion", "cases"}.issubset(
        required_envelope
    )

    cases = contract["requiredCases"]
    assert {case["id"] for case in cases} == REQUIRED_CASE_IDS
    assert {case["javaTest"] for case in cases} == REQUIRED_JAVA_TESTS
    assert {case["model"] for case in cases} == REQUIRED_MODELS
    assert len(cases) == 6


def test_o615_contract_requires_replayable_evidence() -> None:
    contract = _load_json(CONTRACT_PATH)
    required_evidence = set(contract["o615RequiredEvidenceKeys"])

    assert {
        "normalizedRequest",
        "normalizedSql",
        "sqlMarkers",
        "forbiddenSqlMarkers",
        "rows",
        "rowsRequiredFields",
        "rowsForbiddenFields",
    }.issubset(required_evidence)

    for case in contract["requiredCases"]:
        case_evidence = set(case["requiredEvidence"])
        assert "normalizedRequest" in case_evidence
        assert case["requiredSqlMarkers"]
        assert case["forbiddenLeakMarkers"]
        assert case["pythonBoundary"] == "replay-first"

    tenant_case = _case_by_id(contract, "aggregate-join-o615-tenant-guard-no-leak")
    assert {"systemSlice", "fieldAccess", "rowsForbiddenFields"}.issubset(
        set(tenant_case["requiredEvidence"])
    )
    assert "tenantId" in tenant_case["forbiddenLeakMarkers"]

    dimension_case = _case_by_id(contract, "aggregate-join-o615-dimension-id-slice")
    assert "selectedDimensionId" in dimension_case["requiredEvidence"]
    assert "destinationServiceArea" in dimension_case["requiredSqlMarkers"]


def test_manifest_tracks_o615_contract_without_marking_java_exported() -> None:
    manifest = _load_json(MANIFEST_PATH)
    entries = {entry["id"]: entry for entry in manifest["entries"]}
    entry = entries["querymodel-aggregate-join-neutral-snapshots"]

    assert "tests/fixtures/java_querymodel_aggregate_join_o615_snapshot_contract.json" in (
        entry["pythonFixtures"]
    )
    assert (
        "tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py"
        in entry["pythonTests"]
    )
    assert "querymodel-aggregate-join-4" in " ".join(entry["plannedExtensions"])
    assert "querymodel-aggregate-join-4" not in " ".join(entry["javaExported"])


def _case_by_id(contract: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in contract["requiredCases"]:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"Missing O615 aggregate join contract case: {case_id}")
