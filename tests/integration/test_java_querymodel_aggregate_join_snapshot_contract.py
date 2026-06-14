"""Validate the Java QueryModel aggregate-join snapshot contract lane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_querymodel_aggregate_join_snapshot_contract.json"
)
MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_snapshot_parity_manifest.json"
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
    "aggregate-join-orderby-aggregate-output",
    "aggregate-join-return-total",
    "aggregate-join-null-check-outer-only-is-null",
    "aggregate-join-null-check-outer-only-is-not-null",
    "aggregate-join-semantic-debug-extra-diagnostics",
    "aggregate-join-composite-key-pushdown",
    "aggregate-join-structured-access-builder-pushdown",
    "aggregate-join-runtime-filter-unsafe-refusal",
    "aggregate-join-left-dimension-key",
    "aggregate-join-rhs-dimension-fixed-filter",
    "aggregate-join-metadata-lineage",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_schema_and_required_cases() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert contract["schemaVersion"] == 1
    assert contract["feature"] == "queryModelAggregateJoin"
    assert contract["status"] == "contractOnly"
    assert contract["source"] == "JavaQueryModelAggregateJoinSnapshotTest"
    assert contract["contractVersion"] == "querymodel-aggregate-join-3"

    required_envelope = set(contract["requiredEnvelopeFields"])
    assert {"schemaVersion", "feature", "source", "cases"}.issubset(required_envelope)

    case_ids = {case["id"] for case in contract["requiredCases"]}
    assert REQUIRED_CASE_IDS.issubset(case_ids)
    assert len(case_ids) == 29


def test_contract_pins_diagnostics_and_metadata_lineage() -> None:
    contract = _load_json(CONTRACT_PATH)

    diagnostic = contract["diagnosticContract"]
    assert set(diagnostic["requiredDecisionValues"]) == {
        "pushed",
        "retained",
        "refused",
    }
    assert {"decision", "field", "op", "target"}.issubset(
        set(diagnostic["requiredFields"])
    )
    assert "diagnostics" in contract["requiredExpectedFieldsByType"]
    assert "forbiddenMessageMarkers" in contract["optionalExpectedFieldsByType"]["error"]
    assert "returnTotal" in contract["optionalExpectedFieldsByType"]["sql"]

    assert {
        "aggregation",
        "sourceCaption",
        "sourceMeasure",
        "sourceAlias",
        "sourceExpression",
        "aggregateExpression",
        "sourceColumn",
    }.issubset(set(contract["metadataLineageRequiredKeys"]))


def test_manifest_tracks_aggregate_join_as_active_snapshot_lane() -> None:
    manifest = _load_json(MANIFEST_PATH)
    entries = {
        entry["id"]: entry
        for entry in manifest["entries"]
    }
    entry = entries["querymodel-aggregate-join-neutral-snapshots"]

    assert entry["feature"] == "queryModelAggregateJoin"
    assert entry["status"] == "active"
    assert entry["contractFixture"] == (
        "tests/fixtures/java_querymodel_aggregate_join_snapshot_contract.json"
    )
    assert entry["javaExporter"] == (
        "foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/parity/"
        "JavaQueryModelAggregateJoinSnapshotTest.java"
    )
    assert entry["javaExporterStatus"] == "ready"
    assert entry["javaSnapshotOutput"] == (
        "foggy-dataset-model/target/parity/_querymodel_aggregate_join_snapshot.json"
    )
    assert {
        "tests/fixtures/java_querymodel_aggregate_join_snapshot_contract.json",
        "tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json",
        "tests/fixtures/java_querymodel_aggregate_join_o615_snapshot_contract.json",
    }.issubset(set(entry["pythonFixtures"]))
    assert {
        "tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py",
        "tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py",
        "tests/integration/test_java_querymodel_aggregate_join_o615_snapshot_contract.py",
    }.issubset(set(entry["pythonTests"]))
    assert entry["javaExported"]
    assert entry["plannedExtensions"]
